"""
Tests for `enterprise.retirement`.
"""
from pytest import mark

from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from enterprise.api.v1.serializers import EnterpriseGroupMembershipSerializer
from enterprise.models import (
    EnterpriseGroupMembership,
    PendingEnrollment,
    PendingEnterpriseCustomerAdminUser,
    PendingEnterpriseCustomerUser,
)
from enterprise.retirement import (
    redact_and_delete_invites,
    redacted_admin_log_repr,
    redacted_invite_email,
    retire_pending_invites_for_email,
)
from test_utils import factories

LEARNER_HISTORY = PendingEnterpriseCustomerUser.history.model
ADMIN_HISTORY = PendingEnterpriseCustomerAdminUser.history.model


def _log_entry(staff_user, invite):
    """
    Create the admin log entry Django writes when staff change ``invite`` in the admin.
    """
    return LogEntry.objects.create(
        user=staff_user,
        content_type=ContentType.objects.get_for_model(invite),
        object_id=str(invite.pk),
        object_repr=str(invite),
        action_flag=CHANGE,
        change_message='[]',
    )


@mark.django_db
class TestRetirePendingInvitesForEmail(TestCase):
    """
    Tests for `retire_pending_invites_for_email`.
    """

    def setUp(self):
        super().setUp()
        self.email = 'retiring.learner@example.com'
        self.customer = factories.EnterpriseCustomerFactory()
        self.other_customer = factories.EnterpriseCustomerFactory()
        self.learner_invite = factories.PendingEnterpriseCustomerUserFactory(
            enterprise_customer=self.customer, user_email=self.email,
        )
        self.learner_invite.user_email = self.email  # second history version of the same invite
        self.learner_invite.save()
        # Saving an admin invite also creates a learner invite for the same customer and email.
        self.admin_invite = factories.PendingEnterpriseCustomerAdminUserFactory(
            enterprise_customer=self.other_customer, user_email=self.email,
        )
        self.other_invite = factories.PendingEnterpriseCustomerUserFactory(
            enterprise_customer=self.customer, user_email='someone.else@example.com',
        )

    def _history_with_email(self, email):
        return (
            LEARNER_HISTORY.objects.filter(user_email__iexact=email).count()
            + ADMIN_HISTORY.objects.filter(user_email__iexact=email).count()
        )

    def test_deletes_invites_and_history(self):
        assert PendingEnterpriseCustomerUser.objects.filter(user_email=self.email).count() == 2
        assert self._history_with_email(self.email) > 0

        counts = retire_pending_invites_for_email(self.email.upper())

        assert counts['pendingenterprisecustomeruser'] == 2
        assert counts['pendingenterprisecustomeradminuser'] == 1
        assert counts['history_rows'] > 0
        assert not PendingEnterpriseCustomerUser.objects.filter(user_email__iexact=self.email).exists()
        assert not PendingEnterpriseCustomerAdminUser.objects.filter(user_email__iexact=self.email).exists()
        assert self._history_with_email(self.email) == 0
        assert not LEARNER_HISTORY.objects.filter(id=self.learner_invite.id).exists()
        assert not ADMIN_HISTORY.objects.filter(id=self.admin_invite.id).exists()

    def test_leaves_other_learners_untouched(self):
        retire_pending_invites_for_email(self.email)

        self.other_invite.refresh_from_db()
        assert self.other_invite.user_email == 'someone.else@example.com'
        assert LEARNER_HISTORY.objects.filter(id=self.other_invite.id).exists()

    def test_removes_history_of_invites_already_deleted(self):
        """
        An invite deleted earlier (for example when it was accepted) still has history holding the email.
        """
        accepted_invite_id = self.learner_invite.id
        PendingEnterpriseCustomerUser.objects.filter(id=accepted_invite_id).delete()
        assert LEARNER_HISTORY.objects.filter(id=accepted_invite_id, user_email=self.email).exists()

        retire_pending_invites_for_email(self.email)

        assert not LEARNER_HISTORY.objects.filter(id=accepted_invite_id).exists()

    def test_deletes_pending_enrollments_of_the_invite(self):
        factories.PendingEnrollmentFactory(user=self.learner_invite)

        retire_pending_invites_for_email(self.email)

        assert not PendingEnrollment.objects.filter(user_id=self.learner_invite.id).exists()

    def test_never_creates_a_learner_invite_for_the_placeholder(self):
        """
        Saving an admin invite creates a learner invite for its email; blanking must not trigger that.
        """
        retire_pending_invites_for_email(self.email)

        assert not PendingEnterpriseCustomerUser.objects.filter(user_email__endswith='@retired.invalid').exists()
        assert not LEARNER_HISTORY.objects.filter(user_email__endswith='@retired.invalid').exists()

    def test_redacts_admin_log_entries_of_the_invites(self):
        staff = factories.UserFactory(is_staff=True)
        admin_entry = _log_entry(staff, self.admin_invite)
        learner_entry = _log_entry(staff, self.learner_invite)
        other_entry = _log_entry(staff, self.other_invite)
        assert self.email in admin_entry.object_repr

        counts = retire_pending_invites_for_email(self.email)

        assert counts['admin_log_entries'] == 2
        for entry, model, invite in (
            (admin_entry, PendingEnterpriseCustomerAdminUser, self.admin_invite),
            (learner_entry, PendingEnterpriseCustomerUser, self.learner_invite),
        ):
            entry.refresh_from_db()
            assert entry.object_repr == redacted_admin_log_repr(model, invite.id)
            assert self.email not in entry.object_repr
        other_entry.refresh_from_db()
        assert 'someone.else@example.com' in other_entry.object_repr

    def test_idempotent(self):
        _log_entry(factories.UserFactory(is_staff=True), self.learner_invite)
        retire_pending_invites_for_email(self.email)

        counts = retire_pending_invites_for_email(self.email)

        assert counts == {
            'admin_log_entries': 0,
            'group_memberships': 0,
            'history_rows': 0,
            'pendingenterprisecustomeradminuser': 0,
            'pendingenterprisecustomeruser': 0,
        }

    def test_deletes_pending_group_memberships(self):
        """
        Without this, the membership would point at no member and the group learners API could not serialize it.
        """
        membership = factories.EnterpriseGroupMembershipFactory(
            group=factories.EnterpriseGroupFactory(enterprise_customer=self.customer),
            enterprise_customer_user=None,
            pending_enterprise_customer_user=self.learner_invite,
        )
        other_membership = factories.EnterpriseGroupMembershipFactory(
            group=membership.group, enterprise_customer_user=None, pending_enterprise_customer_user=self.other_invite,
        )
        staff = factories.UserFactory(is_staff=True)
        membership_entry = _log_entry(staff, membership)
        other_membership_entry = _log_entry(staff, other_membership)
        assert self.email in membership_entry.object_repr

        counts = retire_pending_invites_for_email(self.email)

        assert counts['group_memberships'] == 1
        assert not EnterpriseGroupMembership.all_objects.filter(uuid=membership.uuid).exists()
        assert EnterpriseGroupMembership.all_objects.filter(uuid=other_membership.uuid).exists()
        members = EnterpriseGroupMembershipSerializer(membership.group.get_all_learners(), many=True).data
        assert [member['member_details'] for member in members] == [{'user_email': 'someone.else@example.com'}]
        membership_entry.refresh_from_db()
        assert membership_entry.object_repr == redacted_admin_log_repr(EnterpriseGroupMembership, membership.uuid)
        other_membership_entry.refresh_from_db()
        assert 'someone.else@example.com' in other_membership_entry.object_repr

    def test_keeps_history_of_an_invite_now_for_another_email(self):
        """
        An admin can change an invite's email. Only the history rows holding the retiring learner's email go.
        """
        invite = factories.PendingEnterpriseCustomerAdminUserFactory(
            enterprise_customer=self.customer, user_email='first.version@example.com',
        )
        ADMIN_HISTORY.objects.filter(id=invite.id).update(user_email=self.email)  # an earlier version had the email
        staff = factories.UserFactory(is_staff=True)
        old_entry = _log_entry(staff, invite)
        LogEntry.objects.filter(pk=old_entry.pk).update(object_repr=f'<Invite {invite.id}>: Acme - {self.email}')
        invite.user_email = 'new.admin@example.com'
        invite.save()
        log_entry = _log_entry(staff, invite)

        retire_pending_invites_for_email(self.email)

        invite.refresh_from_db()
        assert invite.user_email == 'new.admin@example.com'
        assert not ADMIN_HISTORY.objects.filter(user_email__iexact=self.email).exists()
        assert ADMIN_HISTORY.objects.filter(id=invite.id, user_email='new.admin@example.com').exists()
        old_entry.refresh_from_db()
        assert old_entry.object_repr == redacted_admin_log_repr(PendingEnterpriseCustomerAdminUser, invite.id)
        log_entry.refresh_from_db()
        assert 'new.admin@example.com' in log_entry.object_repr


@mark.django_db
class TestRedactAndDeleteInvites(TestCase):
    """
    Tests for `redact_and_delete_invites` and `redacted_invite_email`.
    """

    def test_placeholder_is_per_row_and_never_the_learners_email(self):
        assert redacted_invite_email(7) == 'retired-invite-7@retired.invalid'
        assert redacted_invite_email(7) != redacted_invite_email(8)

    def test_blanks_rows_before_deleting_them(self):
        """
        The warehouse keeps the last values of deleted rows, so each table is blanked before it is deleted.
        """
        invite = factories.PendingEnterpriseCustomerUserFactory(user_email='learner@example.com')
        invite_table = PendingEnterpriseCustomerUser._meta.db_table
        history_table = LEARNER_HISTORY._meta.db_table

        with CaptureQueriesContext(connection) as queries:
            result = redact_and_delete_invites(PendingEnterpriseCustomerUser, [invite.id])

        statements = [query['sql'] for query in queries]

        def first_index(prefix, table):
            return next(
                i for i, sql in enumerate(statements)
                if sql.startswith(prefix) and (f'"{table}"' in sql or f'`{table}`' in sql)
            )

        assert first_index('UPDATE', invite_table) < first_index('DELETE', invite_table)
        assert first_index('UPDATE', history_table) < first_index('DELETE', history_table)
        assert result['invites'] == 1
        assert not PendingEnterpriseCustomerUser.objects.filter(id=invite.id).exists()
        assert not LEARNER_HISTORY.objects.filter(id=invite.id).exists()

    def test_skips_ids_that_no_longer_exist(self):
        assert redact_and_delete_invites(PendingEnterpriseCustomerUser, [123456]) == {
            'invites': 0, 'group_memberships': 0, 'history_rows': 0, 'admin_log_entries': 0,
        }
