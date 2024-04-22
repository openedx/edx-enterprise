"""
Tests for the `edx-enterprise` models module.
"""

import unittest
from collections import OrderedDict
from datetime import datetime
from unittest import mock

import ddt
from pytest import mark

from django.db import transaction
from django.test import override_settings

from enterprise.constants import ENTERPRISE_ADMIN_ROLE, ENTERPRISE_LEARNER_ROLE
from enterprise.models import (
    EnterpriseCourseEnrollment,
    EnterpriseCustomerCatalog,
    EnterpriseCustomerUser,
    EnterpriseGroupMembership,
    PendingEnrollment,
    PendingEnterpriseCustomerAdminUser,
    PendingEnterpriseCustomerUser,
    SystemWideEnterpriseRole,
    SystemWideEnterpriseUserRoleAssignment,
)
from enterprise.signals import create_enterprise_enrollment_receiver, handle_user_post_save
from integrated_channels.integrated_channel.models import OrphanedContentTransmissions
from test_utils import EmptyCacheMixin
from test_utils.factories import (
    ContentMetadataItemTransmissionFactory,
    EnterpriseCatalogQueryFactory,
    EnterpriseCustomerCatalogFactory,
    EnterpriseCustomerFactory,
    EnterpriseCustomerUserFactory,
    EnterpriseGroupMembershipFactory,
    PendingEnrollmentFactory,
    PendingEnterpriseCustomerAdminUserFactory,
    PendingEnterpriseCustomerUserFactory,
    SAPSuccessFactorsEnterpriseCustomerConfigurationFactory,
    SystemWideEnterpriseUserRoleAssignmentFactory,
    UserFactory,
)


@mark.django_db(transaction=True)
@ddt.ddt
class TestUserPostSaveSignalHandler(EmptyCacheMixin, unittest.TestCase):
    """
    Test User post_save signal handler.
    """
    def test_handle_user_post_save_no_user_instance_nothing_happens(self):
        # precondition checks
        assert PendingEnterpriseCustomerUser.objects.count() == 0
        assert EnterpriseCustomerUser.objects.count() == 0

        parameters = {"instance": None, "created": False}
        with transaction.atomic():
            handle_user_post_save(mock.Mock(), **parameters)

        assert PendingEnterpriseCustomerUser.objects.count() == 0
        assert EnterpriseCustomerUser.objects.count() == 0

    def test_handle_user_post_save_no_matching_pending_link(self):
        user = UserFactory(email="jackie.chan@hollywood.com")

        assert PendingEnterpriseCustomerUser.objects.count() == 0, "Precondition check: no pending links available"
        assert EnterpriseCustomerUser.objects.count() == 0, "Precondition check: no links exists"

        parameters = {"instance": user, "created": True}
        handle_user_post_save(mock.Mock(), **parameters)

        assert PendingEnterpriseCustomerUser.objects.count() == 0
        assert EnterpriseCustomerUser.objects.count() == 0

    def test_handle_user_post_save_created_user(self):
        email = "jackie.chan@hollywood.com"
        user = UserFactory(id=1, email=email)
        pending_link = PendingEnterpriseCustomerUserFactory(user_email=email)

        assert EnterpriseCustomerUser.objects.filter(user_id=user.id).count() == 0, "Precondition check: no links exist"
        assert PendingEnterpriseCustomerUser.objects.filter(user_email=email).count() == 1, \
            "Precondition check: pending link exists"

        parameters = {"instance": user, "created": True}
        with transaction.atomic():
            handle_user_post_save(mock.Mock(), **parameters)

        assert PendingEnterpriseCustomerUser.objects.count() == 0
        assert EnterpriseCustomerUser.objects.filter(
            enterprise_customer=pending_link.enterprise_customer, user_id=user.id
        ).count() == 1

    def test_handle_user_post_save_created_user_multiple_enterprises(self):
        email = "jackie.chan@hollywood.com"
        user = UserFactory(id=1, email=email)
        enterprise_customer = EnterpriseCustomerFactory()
        enterprise_customer_2 = EnterpriseCustomerFactory()
        PendingEnterpriseCustomerUserFactory(enterprise_customer=enterprise_customer, user_email=email)
        PendingEnterpriseCustomerUserFactory(enterprise_customer=enterprise_customer_2, user_email=email)

        assert EnterpriseCustomerUser.objects.filter(user_id=user.id).count() == 0, "Precondition check: no links exist"
        assert PendingEnterpriseCustomerUser.objects.filter(user_email=email).count() == 2, \
            "Precondition check: pending link exists"

        parameters = {"instance": user, "created": True}
        with transaction.atomic():
            handle_user_post_save(mock.Mock(), **parameters)

        assert PendingEnterpriseCustomerUser.objects.count() == 0
        assert EnterpriseCustomerUser.objects.filter(
            enterprise_customer=enterprise_customer, user_id=user.id
        ).count() == 1
        assert EnterpriseCustomerUser.objects.filter(
            enterprise_customer=enterprise_customer_2, user_id=user.id
        ).count() == 1

    def test_handle_user_post_save_modified_user_not_linked(self):
        email = "jackie.chan@hollywood.com"
        user = UserFactory(id=1, email=email)
        pending_link = PendingEnterpriseCustomerUserFactory(user_email=email)

        assert EnterpriseCustomerUser.objects.filter(user_id=user.id).count() == 0, "Precondition check: no links exist"
        assert PendingEnterpriseCustomerUser.objects.filter(user_email=email).count() == 1, \
            "Precondition check: pending link exists"

        parameters = {"instance": user, "created": False}
        with transaction.atomic():
            handle_user_post_save(mock.Mock(), **parameters)

        assert PendingEnterpriseCustomerUser.objects.count() == 0
        assert EnterpriseCustomerUser.objects.filter(
            enterprise_customer=pending_link.enterprise_customer, user_id=user.id
        ).count() == 1

    @mock.patch('enterprise.utils.track_event')
    @mock.patch('enterprise.models.track_enrollment')
    @mock.patch('enterprise.models.EnrollmentApiClient')
    def test_handle_user_post_save_with_pending_course_enrollment(
            self,
            mock_course_enrollment,
            mock_track_enrollment,
            mock_track_event  # pylint: disable=unused-argument
    ):
        mock_course_enrollment.enroll.return_value = None
        email = "fake_email@edx.org"
        user = UserFactory(id=1, email=email)
        pending_link = PendingEnterpriseCustomerUserFactory(user_email=email)
        pending_link.enterprise_customer.enable_autocohorting = True
        pending_link.enterprise_customer.save()
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        PendingEnrollmentFactory(user=pending_link, course_id=course_id, cohort_name='test_cohort')

        assert EnterpriseCustomerUser.objects.filter(user_id=user.id).count() == 0, "Precondition check: no links exist"
        assert PendingEnterpriseCustomerUser.objects.filter(user_email=email).count() == 1, \
            "Precondition check: pending link exists"
        assert PendingEnrollment.objects.filter(user=pending_link).count() == 1, \
            'Precondition check: only one enrollment exists.'

        mock_course_enrollment.return_value = mock.Mock(
            get_course_enrollment=mock.Mock(
                side_effect=[None, {'is_active': False, 'mode': 'verified'}]
            ),
            enroll_user_in_course=mock.Mock()
        )
        parameters = {'instance': user, "created": False}
        with transaction.atomic():
            handle_user_post_save(mock.Mock(), **parameters)
        assert PendingEnterpriseCustomerUser.objects.count() == 0
        assert EnterpriseCustomerUser.objects.filter(
            enterprise_customer=pending_link.enterprise_customer, user_id=user.id
        ).count() == 1
        assert PendingEnrollment.objects.count() == 0
        assert EnterpriseCourseEnrollment.objects.count() == 1
        mock_course_enrollment.return_value.enroll_user_in_course.assert_called_once_with(
            user.username,
            course_id,
            'audit',
            cohort='test_cohort',
            enterprise_uuid=str(pending_link.enterprise_customer.uuid)
        )
        mock_track_enrollment.assert_called_once_with('pending-admin-enrollment', user.id, course_id)

    def test_handle_user_post_save_with_pending_enterprise_admin(self):
        email = "jackie.chan@hollywood.com"
        user = UserFactory(id=1, email=email)
        enterprise_customer = EnterpriseCustomerFactory()
        PendingEnterpriseCustomerAdminUserFactory(enterprise_customer=enterprise_customer, user_email=email)

        assert PendingEnterpriseCustomerAdminUser.objects.filter(user_email=email).count() == 1, \
            "Precondition check: pending admin user exists"

        parameters = {"instance": user, "created": False}
        handle_user_post_save(mock.Mock(), **parameters)

        assert EnterpriseCustomerUser.objects.filter(user_id=user.id).count() == 1, \
            "Precondition check: enterprise customer user exists"

        enterprise_admin_role, __ = SystemWideEnterpriseRole.objects.get_or_create(name=ENTERPRISE_ADMIN_ROLE)
        admin_role_assignment = SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user=user,
            role=enterprise_admin_role,
        )
        assert admin_role_assignment.exists()

        assert PendingEnterpriseCustomerAdminUser.objects.filter(user_email=email).count() == 0, \
            "Final check: pending admin user no longer exists"

    def test_handle_user_post_save_modified_user_already_linked(self):
        email = "jackie.chan@hollywood.com"
        user = UserFactory(id=1, email=email)
        enterprise_customer1, enterprise_customer2 = EnterpriseCustomerFactory(), EnterpriseCustomerFactory()
        EnterpriseCustomerUserFactory(enterprise_customer=enterprise_customer1, user_id=user.id)
        PendingEnterpriseCustomerUserFactory(enterprise_customer=enterprise_customer2, user_email=email)

        assert EnterpriseCustomerUser.objects.filter(user_id=user.id).count() == 1, "Precondition check: links exists"
        assert PendingEnterpriseCustomerUser.objects.filter(user_email=email).count() == 1, \
            "Precondition check: pending link exists"

        parameters = {"instance": user, "created": False}
        handle_user_post_save(mock.Mock(), **parameters)

        assert EnterpriseCustomerUser.objects.filter(user_id=user.id).count() == 2, "Should return 2 existing links"

        link_1 = EnterpriseCustomerUser.objects.get(
            user_id=user.id,
            enterprise_customer=enterprise_customer1,
        )
        link_2 = EnterpriseCustomerUser.objects.get(
            user_id=user.id,
            enterprise_customer=enterprise_customer2,
        )
        assert link_1.enterprise_customer == enterprise_customer1
        assert link_2.enterprise_customer == enterprise_customer2

        assert PendingEnterpriseCustomerUser.objects.count() == 0, "Should delete pending link"

    def test_handle_user_post_save_raw(self):
        email = "jackie.chan@hollywood.com"
        user = UserFactory(id=1, email=email)
        PendingEnterpriseCustomerUserFactory(user_email=email)

        assert EnterpriseCustomerUser.objects.filter(user_id=user.id).count() == 0, "Precondition check: no links exist"
        assert PendingEnterpriseCustomerUser.objects.filter(user_email=email).count() == 1, \
            "Precondition check: pending link exists"

        parameters = {"instance": user, "created": False, "raw": True}
        handle_user_post_save(mock.Mock(), **parameters)

        assert EnterpriseCustomerUser.objects.filter(user_id=user.id).count() == 0, "Link have been created"
        assert PendingEnterpriseCustomerUser.objects.filter(user_email=email).count() == 1, \
            "Pending link should be kept"

    def test_handle_user_post_save_fulfills_pending_group_memberships(self):
        email = "jackie.chan@hollywood.com"
        user = UserFactory(id=1, email=email)
        pending_user = PendingEnterpriseCustomerUserFactory(user_email=email)
        new_membership = EnterpriseGroupMembershipFactory(
            pending_enterprise_customer_user=pending_user,
            enterprise_customer_user=None
        )
        assert not new_membership.activated_at
        assert new_membership.status == 'pending'

        parameters = {"instance": user, "created": False}
        handle_user_post_save(mock.Mock(), **parameters)
        # Should delete pending link
        assert PendingEnterpriseCustomerUser.objects.count() == 0
        assert len(EnterpriseGroupMembership.objects.all()) == 1

        new_enterprise_user = EnterpriseCustomerUser.objects.get(user_id=user.id)
        membership = EnterpriseGroupMembership.objects.first()
        assert membership.pending_enterprise_customer_user is None
        assert membership.enterprise_customer_user == new_enterprise_user
        assert membership.activated_at
        assert membership.status == 'accepted'


@mark.django_db
@ddt.ddt
class TestDefaultContentFilter(unittest.TestCase):
    """
    Tests for the content_filter field of the EnterpriseCustomerCatalog model.
    """

    @ddt.data(
        (
            {
                'content_type': 'course',
                'partner': 'edx'
            },
            {
                'content_type': 'course',
                'partner': 'edx'
            }
        ),
        (
            {
                'content_type': 'course',
                'level_type': [
                    'Introductory',
                    'Intermediate'
                ],
                'availability': [
                    'Current',
                    'Starting Soon',
                    'Upcoming'
                ],
                'status': 'published'
            },
            {
                'content_type': 'course',
                'level_type': [
                    'Introductory',
                    'Intermediate'
                ],
                'availability': [
                    'Current',
                    'Starting Soon',
                    'Upcoming'
                ],
                'status': 'published'
            }
        ),
        # if the value is not set is settings, it picks default value from constant.
        (
            {},
            {'content_type': 'course'}
        )
    )
    @ddt.unpack
    @mock.patch('enterprise.utils.DEFAULT_CATALOG_CONTENT_FILTER', {'content_type': 'course'})
    def test_default_content_filter(self, default_content_filter, expected_content_filter):
        """
        Test that `EnterpriseCustomerCatalog`.content_filter is saved with correct default content filter.
        """
        with override_settings(ENTERPRISE_CUSTOMER_CATALOG_DEFAULT_CONTENT_FILTER=default_content_filter):
            enterprise_catalog = EnterpriseCustomerCatalogFactory(enterprise_catalog_query=None)
            assert enterprise_catalog.content_filter == expected_content_filter


@mark.django_db
class TestPendingEnterpriseAdminUserSignals(unittest.TestCase):
    """
    Test signals associated with PendingEnterpriseCustomerAdminUser.
    """

    def setUp(self):
        """
        Setup for `TestPendingEnterpriseAdminUserSignals` test.
        """
        self.admin_user = UserFactory(id=2, email='user@example.com')
        self.enterprise_customer = EnterpriseCustomerFactory()
        super().setUp()

    def _assert_pending_ecus_exist(self, should_exist=True):
        """
        Assert whether ``PendingEnterpriseCustomerUser`` record(s) exist for the specified user
        and enterprise customer.
        """
        pending_ecus = PendingEnterpriseCustomerUser.objects.filter(
            user_email=self.admin_user.email,
            enterprise_customer=self.enterprise_customer,
        )
        assert should_exist == pending_ecus.exists()

    def test_create_pending_enterprise_admin_user(self):
        """
        Assert that creating a ``PendingEnterpriseCustomerAdminUser`` creates a ``PendingEnterpriseCustomerUser``.
        """
        # verify that PendingEnterpriseCustomerUser record does not yet exist.
        self._assert_pending_ecus_exist(should_exist=False)

        # create new PendingEnterpriseCustomerAdminUser
        PendingEnterpriseCustomerAdminUserFactory(
            user_email=self.admin_user.email,
            enterprise_customer=self.enterprise_customer,
        )

        # verify that PendingEnterpriseCustomerUser record was created.
        self._assert_pending_ecus_exist()

    def test_delete_pending_enterprise_admin_user(self):
        """
        Assert that deleting a ``PendingEnterpriseCustomerAdminUser`` deletes its ``PendingEnterpriseCustomerUser``.
        """
        # create new PendingEnterpriseCustomerAdminUser
        PendingEnterpriseCustomerAdminUserFactory(
            user_email=self.admin_user.email,
            enterprise_customer=self.enterprise_customer,
        )

        # verify that PendingEnterpriseCustomerUser record exists.
        self._assert_pending_ecus_exist()

        # delete the PendingEnterpriseCustomerAdminUser record and verify that the
        # associated PendingEnterpriseCustomerUser is also deleted.
        PendingEnterpriseCustomerAdminUser.objects.filter(
            user_email=self.admin_user.email,
            enterprise_customer=self.enterprise_customer,
        ).delete()
        self._assert_pending_ecus_exist(should_exist=False)


@mark.django_db
@ddt.ddt
class TestEnterpriseAdminRoleSignals(unittest.TestCase):
    """
    Test signals associated with EnterpriseCustomerUser and the enterprise_admin role.
    """

    def setUp(self):
        """
        Setup for `TestEnterpriseAdminRoleSignals` test.
        """
        self.enterprise_admin_role, __ = SystemWideEnterpriseRole.objects.get_or_create(name=ENTERPRISE_ADMIN_ROLE)
        self.admin_user = UserFactory(id=2, email='user@example.com')
        self.enterprise_customer = EnterpriseCustomerFactory()
        super().setUp()

    def test_delete_enterprise_admin_role_assignment_success(self):
        """
        Test that when `EnterpriseCustomerUser` record is deleted, the associated
        enterprise admin user role assignment is also deleted.
        """
        # create new EnterpriseCustomerUser and SystemWideEnterpriseUserRoleAssignment records.
        EnterpriseCustomerUserFactory(
            user_id=self.admin_user.id,
            enterprise_customer=self.enterprise_customer,
        )
        SystemWideEnterpriseUserRoleAssignmentFactory(
            user=self.admin_user,
            role=self.enterprise_admin_role,
            enterprise_customer=self.enterprise_customer,
        )

        # verify that a new admin role assignment was created.
        admin_role_assignments = SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user=self.admin_user,
            role=self.enterprise_admin_role,
            enterprise_customer=self.enterprise_customer,
        )
        self.assertTrue(admin_role_assignments.exists())

        # delete EnterpriseCustomerUser record and verify that admin role assignment is deleted as well.
        EnterpriseCustomerUser.objects.filter(user_id=self.admin_user.id).delete()
        admin_role_assignments = SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user=self.admin_user,
            role=self.enterprise_admin_role,
            enterprise_customer=self.enterprise_customer,
        )
        self.assertFalse(admin_role_assignments.exists())


@mark.django_db
@ddt.ddt
class TestEnterpriseLearnerRoleSignals(unittest.TestCase):
    """
    Tests signals associated with EnterpriseCustomerUser and the enterprise_learner role.
    """
    def setUp(self):
        """
        Setup for `TestEnterpriseLearnerRoleSignals` test.
        """
        self.enterprise_learner_role, __ = SystemWideEnterpriseRole.objects.get_or_create(name=ENTERPRISE_LEARNER_ROLE)
        self.learner_user = UserFactory(id=2, email='user@example.com')
        self.enterprise_customer = EnterpriseCustomerFactory(
            name='Team Titans',
        )
        self.second_enterprise_customer = EnterpriseCustomerFactory(
            name='Duke',
        )
        super().setUp()

    def test_assign_enterprise_learner_role_success(self):
        """
        Test that when a new `EnterpriseCustomerUser` record is created, `assign_enterprise_learner_role` assigns an
        enterprise learner role to it.
        """
        enterprise_customer_user = EnterpriseCustomerUser.objects.filter(
            user_id=self.learner_user.id
        )
        self.assertFalse(enterprise_customer_user.exists())

        # Verify that no learner role assignment exists.
        learner_role_assignment = SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user=self.learner_user,
            role=self.enterprise_learner_role
        )
        self.assertFalse(learner_role_assignment.exists())

        # Create a new EnterpriseCustomerUser record.
        EnterpriseCustomerUserFactory(
            user_id=self.learner_user.id,
            enterprise_customer=self.enterprise_customer,
        )

        enterprise_customer_user = EnterpriseCustomerUser.objects.filter(
            user_id=self.learner_user.id
        )
        self.assertTrue(enterprise_customer_user.exists())

        # Verify that now a new learner role assignment is created.
        learner_role_assignment = SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user=self.learner_user,
            role=self.enterprise_learner_role
        )
        self.assertTrue(learner_role_assignment.exists())

    def test_enterprise_learner_role_post_save_create(self):
        """
        Test that the "enterprise_learner" role is created when a new EnterpriseCustomerUser
        record is created.
        """
        # Create a new EnterpriseCustomerUser record.
        EnterpriseCustomerUserFactory(
            user_id=self.learner_user.id,
            enterprise_customer=self.enterprise_customer,
        )
        learner_role_assignments = SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user=self.learner_user,
            role=self.enterprise_learner_role,
            enterprise_customer=self.enterprise_customer,
        )
        self.assertTrue(learner_role_assignments.exists())

    def test_enterprise_learner_role_post_save_update(self):
        """
        Test "enterprise_learner" role is deleted when an EnterpriseCustomerUser
        record is unlinked and that the "enterprise_learner" role is created when the
        same EnterpriseCustomerUser record is re-linked.
        """
        # Create a new EnterpriseCustomerUser record
        EnterpriseCustomerUserFactory(
            user_id=self.learner_user.id,
            enterprise_customer=self.enterprise_customer,
        )

        # Verify "enterprise_learner" role now exists
        learner_role_assignments = SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user=self.learner_user,
            role=self.enterprise_learner_role,
            enterprise_customer=self.enterprise_customer,
        )
        self.assertTrue(learner_role_assignments.exists())

        # Unlink EnterpriseCustomerUser record
        enterprise_customer_user = EnterpriseCustomerUser.objects.get(
            user_id=self.learner_user.id,
        )
        enterprise_customer_user.linked = False
        enterprise_customer_user.save()

        # Verify "enterprise_learner" role is deleted when unlinking an EnterpriseCustomerUser
        learner_role_assignments = SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user=self.learner_user,
            role=self.enterprise_learner_role
        )
        self.assertFalse(learner_role_assignments.exists())

        # Re-link EnterpriseCustomerUser record
        enterprise_customer_user.linked = True
        enterprise_customer_user.save()

        # Verify "enterprise_learner" role now exists again
        learner_role_assignments = SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user=self.learner_user,
            role=self.enterprise_learner_role,
            enterprise_customer=self.enterprise_customer,
        )
        self.assertTrue(learner_role_assignments.exists())

    def test_assign_enterprise_learner_role_no_user_association(self):
        """
        Test that `assign_enterprise_learner_role` does not do anything if no User object is not associated with
        `EnterpriseCustomerUser` record.
        """
        # Verify that no learner role assignment exists.
        learner_role_assignment = SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user=self.learner_user,
            role=self.enterprise_learner_role
        )
        self.assertFalse(learner_role_assignment.exists())

        # Create a new EnterpriseCustomerUser with no user associated.
        EnterpriseCustomerUserFactory(
            enterprise_customer=self.enterprise_customer,
        )

        # Verify that no learner role assignment exists.
        learner_role_assignment = SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user=self.learner_user,
            role=self.enterprise_learner_role
        )
        self.assertFalse(learner_role_assignment.exists())

    def test_delete_enterprise_learner_role_assignment_success(self):
        """
        Test that when `EnterpriseCustomerUser` record is deleted, `delete_enterprise_learner_role_assignment` also
        deletes the enterprise learner role assignment associated with it.
        """
        # Create a new EnterpriseCustomerUser record.
        EnterpriseCustomerUserFactory(
            user_id=self.learner_user.id,
            enterprise_customer=self.enterprise_customer,
        )

        enterprise_customer_user = EnterpriseCustomerUser.objects.filter(
            user_id=self.learner_user.id
        )
        self.assertTrue(enterprise_customer_user.exists())

        # Verify that now a new learner role assignment is created.
        learner_role_assignment = SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user=self.learner_user,
            role=self.enterprise_learner_role
        )
        self.assertTrue(learner_role_assignment.exists())

        # Delete EnterpriseCustomerUser record.
        enterprise_customer_user.delete()

        # Verify that enterprise_customer_user is deleted
        enterprise_customer_user = EnterpriseCustomerUser.objects.filter(
            user_id=self.learner_user.id
        )
        self.assertFalse(enterprise_customer_user.exists())

        # Also verify that learner role assignment is deleted as well.
        learner_role_assignment = SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user=self.learner_user,
            role=self.enterprise_learner_role
        )
        self.assertFalse(learner_role_assignment.exists())

    def test_delete_single_enterprise_learner_role_assignment(self):
        """
        Test that when `EnterpriseCustomerUser` record is deleted, `delete_enterprise_learner_role_assignment`
        also deletes the enterprise learner role assignment associated with the user's previously linked enterprise
        customer. However. it should *not* delete the enterprise learner role assignment associated with other
        enterprise customers.
        """
        # Create a new EnterpriseCustomerUser record.
        EnterpriseCustomerUserFactory(
            user_id=self.learner_user.id,
            enterprise_customer=self.enterprise_customer,
        )

        # Create a EnterpriseCustomerUser record such that the user is linked to multiple enterprises.
        EnterpriseCustomerUserFactory(
            user_id=self.learner_user.id,
            enterprise_customer=self.second_enterprise_customer,
        )

        # Verify that a new learner role assignment is created for both linked enterprise customers.
        learner_role_assignment = SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user=self.learner_user,
            role=self.enterprise_learner_role,
            enterprise_customer=self.enterprise_customer,
        )
        self.assertTrue(learner_role_assignment.exists())
        second_learner_role_assignment = SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user=self.learner_user,
            role=self.enterprise_learner_role,
            enterprise_customer=self.second_enterprise_customer,
        )
        self.assertTrue(second_learner_role_assignment.exists())

        # Delete EnterpriseCustomerUser record.
        enterprise_customer_user = EnterpriseCustomerUser.objects.get(
            user_id=self.learner_user.id,
            enterprise_customer=self.enterprise_customer,
        )
        enterprise_customer_user.delete()

        # Verify appropriate learner role assignment is deleted, but the other
        # learner role assignment remains.
        learner_role_assignment = SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user=self.learner_user,
            role=self.enterprise_learner_role,
            enterprise_customer=self.enterprise_customer,
        )
        self.assertFalse(learner_role_assignment.exists())
        second_learner_role_assignment = SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user=self.learner_user,
            role=self.enterprise_learner_role,
            enterprise_customer=self.second_enterprise_customer,
        )
        self.assertTrue(second_learner_role_assignment.exists())

    def test_unlink_single_enterprise_learner_role_assignment(self):
        """
        Test that when `EnterpriseCustomerUser` record is unlinked, `assign_or_delete_enterprise_learner_role`
        also deletes the enterprise learner role assignment associated with the user's previously linked enterprise
        customer. However. it should *not* delete the enterprise learner role assignment associated with other
        enterprise customers.
        """
        # Create a new EnterpriseCustomerUser record.
        EnterpriseCustomerUserFactory(
            user_id=self.learner_user.id,
            enterprise_customer=self.enterprise_customer,
        )

        # Create a EnterpriseCustomerUser record such that the user is linked to multiple enterprises.
        EnterpriseCustomerUserFactory(
            user_id=self.learner_user.id,
            enterprise_customer=self.second_enterprise_customer,
        )

        # Verify that a new learner role assignment is created for both linked enterprise customers.
        learner_role_assignment = SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user=self.learner_user,
            role=self.enterprise_learner_role,
            enterprise_customer=self.enterprise_customer,
        )
        self.assertTrue(learner_role_assignment.exists())
        second_learner_role_assignment = SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user=self.learner_user,
            role=self.enterprise_learner_role,
            enterprise_customer=self.second_enterprise_customer,
        )
        self.assertTrue(second_learner_role_assignment.exists())

        # Unlink EnterpriseCustomerUser record.
        enterprise_customer_user = EnterpriseCustomerUser.objects.get(
            user_id=self.learner_user.id,
            enterprise_customer=self.enterprise_customer,
        )
        enterprise_customer_user.linked = False
        enterprise_customer_user.save()

        # Verify appropriate learner role assignment is deleted, but the other
        # learner role assignment remains.
        learner_role_assignment = SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user=self.learner_user,
            role=self.enterprise_learner_role,
            enterprise_customer=self.enterprise_customer,
        )
        self.assertFalse(learner_role_assignment.exists())
        second_learner_role_assignment = SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user=self.learner_user,
            role=self.enterprise_learner_role,
            enterprise_customer=self.second_enterprise_customer,
        )
        self.assertTrue(second_learner_role_assignment.exists())

    def test_delete_enterprise_learner_role_assignment_no_role_assignment(self):
        """
        Test that when if no role assignment is associated with a deleted `EnterpriseCustomerUser` record,
        `delete_enterprise_learner_role_assignment` does nothing.
        """
        # Create a new EnterpriseCustomerUser record.
        EnterpriseCustomerUserFactory(
            user_id=self.learner_user.id,
            enterprise_customer=self.enterprise_customer,
        )

        enterprise_customer_user = EnterpriseCustomerUser.objects.filter(
            user_id=self.learner_user.id
        )
        self.assertTrue(enterprise_customer_user.exists())

        # Delete the role assignment record for tesing purposes.
        learner_role_assignment = SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user=self.learner_user,
            role=self.enterprise_learner_role
        )
        learner_role_assignment.delete()

        # Delete EnterpriseCustomerUser record.
        enterprise_customer_user.delete()

        # Verify that enterprise_customer_user is deleted
        enterprise_customer_user = EnterpriseCustomerUser.objects.filter(
            user_id=self.learner_user.id
        )
        self.assertFalse(enterprise_customer_user.exists())

        # Also verify that no new learner role assignment is created hence won't be deleted.
        learner_role_assignment = SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user=self.learner_user,
            role=self.enterprise_learner_role
        )
        self.assertFalse(learner_role_assignment.exists())

    def test_delete_enterprise_learner_role_assignment_no_user_associated(self):
        """
        Test that when if no user is associated with a deleted `EnterpriseCustomerUser` record,
        `delete_enterprise_learner_role_assignment` does nothing.
        """
        # Create a new EnterpriseCustomerUser with no user associated.
        EnterpriseCustomerUserFactory(
            enterprise_customer=self.enterprise_customer,
        )

        enterprise_customer_user = EnterpriseCustomerUser.objects.filter(
            enterprise_customer=self.enterprise_customer
        )
        self.assertTrue(enterprise_customer_user.exists())

        # Verify that no new learner role assignment is created.
        learner_role_assignment = SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user=self.learner_user,
            role=self.enterprise_learner_role
        )
        self.assertFalse(learner_role_assignment.exists())

        # Delete EnterpriseCustomerUser record.
        enterprise_customer_user.delete()

        # Verify that enterprise_customer_user is deleted
        enterprise_customer_user = EnterpriseCustomerUser.objects.filter(
            enterprise_customer=self.enterprise_customer
        )
        self.assertFalse(enterprise_customer_user.exists())

        # Also verify that no new learner role assignment is created hence won't be deleted.
        learner_role_assignment = SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user=self.learner_user,
            role=self.enterprise_learner_role
        )
        self.assertFalse(learner_role_assignment.exists())


@mark.django_db
class TestCourseEnrollmentSignals(unittest.TestCase):
    """
    Tests signals associated with CourseEnrollments (that are found in edx-platform).
    """
    def setUp(self):
        """
        Setup for `TestCourseEnrollmentSignals` test.
        """
        self.user = UserFactory(id=2, email='user@example.com')
        self.enterprise_customer = EnterpriseCustomerFactory(
            name='Team Titans',
        )
        self.enterprise_customer_user = EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=self.enterprise_customer,
        )
        self.non_enterprise_user = UserFactory(id=999, email='user999@example.com')
        super().setUp()

    @mock.patch('enterprise.tasks.create_enterprise_enrollment.delay')
    def test_receiver_calls_task_if_ecu_exists(self, mock_task):
        """
        Receiver should call a task
        if user tied to the CourseEnrollment that is handed into the function
        is an EnterpriseCustomerUser
        """
        sender = mock.Mock()  # This would be a CourseEnrollment class
        instance = mock.Mock()  # This would be a CourseEnrollment instance
        instance.user = self.user
        instance.course_id = "fake:course_id"
        # Signal metadata (note: 'signal' would be an actual object, but we dont need it here)
        kwargs = {
            'update_fields': None,
            'raw': False,
            'signal': '<django.db.models.signals.ModelSignal object at 0x7fcfc38b5e90>',
            'using': 'default',
            'created': True,
        }

        create_enterprise_enrollment_receiver(sender, instance, **kwargs)
        mock_task.assert_called_once_with(str(instance.course_id), self.enterprise_customer_user.id)

    @mock.patch('enterprise.tasks.create_enterprise_enrollment.delay')
    def test_receiver_does_not_call_task_if_ecu_not_exists(self, mock_task):
        """
        Receiver should NOT call a task
        if user tied to the CourseEnrollment that is handed into the function
        is NOT an EnterpriseCustomerUser
        """
        sender = mock.Mock()  # This would be a CourseEnrollment class
        instance = mock.Mock()  # This would be a CourseEnrollment instance
        instance.user = self.non_enterprise_user
        instance.course_id = "fake:course_id"
        # Signal metadata (note: 'signal' would be an actual object, but we dont need it here)
        kwargs = {
            'update_fields': None,
            'raw': False,
            'signal': '<django.db.models.signals.ModelSignal object at 0x7fcfc38b5e90>',
            'using': 'default',
            'created': True,
        }

        create_enterprise_enrollment_receiver(sender, instance, **kwargs)
        mock_task.assert_not_called()


@mark.django_db
class TestEnterpriseCatalogSignals(unittest.TestCase):
    """
    Tests the EnterpriseCustomerCatalogAdmin
    """

    @mock.patch('enterprise.signals.EnterpriseCatalogApiClient')
    def test_delete_catalog(self, api_client_mock):
        enterprise_catalog = EnterpriseCustomerCatalogFactory()
        enterprise_catalog_uuid = enterprise_catalog.uuid
        api_client_mock.return_value.get_enterprise_catalog.return_value = True
        enterprise_catalog.delete()

        # Verify the API was called correctly and the catalog was deleted
        api_client_mock.return_value.delete_enterprise_catalog.assert_called_with(enterprise_catalog_uuid)
        self.assertFalse(EnterpriseCustomerCatalog.objects.exists())

    @mock.patch('enterprise.signals.EnterpriseCatalogApiClient')
    def test_delete_catalog_cleaning_up_orphaned_content_transmission_items(self, api_client_mock):
        """
        Tests that when an EnterpriseCustomerCatalog is deleted, any associated
        Integrated Channels content metadata records are also marked as orphaned.
        """
        api_client_mock.return_value.get_enterprise_catalog.return_value = True
        customer = EnterpriseCustomerFactory()
        enterprise_catalog_to_be_deleted = EnterpriseCustomerCatalogFactory(enterprise_customer=customer)
        enterprise_catalog_to_be_kept = EnterpriseCustomerCatalogFactory(enterprise_customer=customer)

        customer.enterprise_customer_catalogs.set([enterprise_catalog_to_be_deleted, enterprise_catalog_to_be_kept])
        customer.save()
        integrated_channels_config = SAPSuccessFactorsEnterpriseCustomerConfigurationFactory(
            enterprise_customer=customer,
        )
        # A record that would be orphaned if the test catalog is deleted
        orphaned_content_transmission_item = ContentMetadataItemTransmissionFactory(
            integrated_channel_code=integrated_channels_config.channel_code(),
            enterprise_customer=customer,
            plugin_configuration_id=integrated_channels_config.id,
            enterprise_customer_catalog_uuid=enterprise_catalog_to_be_deleted.uuid,
            remote_deleted_at=None,
            remote_created_at=datetime.now(),
        )
        # A normal record that is unaffected by the test catalog deletion
        ContentMetadataItemTransmissionFactory(
            integrated_channel_code=integrated_channels_config.channel_code(),
            enterprise_customer=customer,
            plugin_configuration_id=integrated_channels_config.id,
            enterprise_customer_catalog_uuid=enterprise_catalog_to_be_kept.uuid,
            remote_deleted_at=None,
            remote_created_at=datetime.now(),
        )
        enterprise_catalog_to_be_deleted.delete()

        assert OrphanedContentTransmissions.objects.all().count() == 1
        assert OrphanedContentTransmissions.objects.filter(id=orphaned_content_transmission_item.id).exists()

    @mock.patch('enterprise.signals.EnterpriseCatalogApiClient')
    def test_create_catalog(self, api_client_mock):
        api_client_mock.return_value.get_enterprise_catalog.return_value = {}
        enterprise_catalog = EnterpriseCustomerCatalogFactory()

        # Verify the API was called and the catalog "was created" (even though it already was)
        # This method is a little weird in that the object is sort of created / not-created at the same time
        api_client_mock.return_value.create_enterprise_catalog.assert_called_with(
            str(enterprise_catalog.uuid),
            str(enterprise_catalog.enterprise_customer.uuid),
            enterprise_catalog.enterprise_customer.name,
            enterprise_catalog.title,
            enterprise_catalog.content_filter,
            enterprise_catalog.enabled_course_modes,
            enterprise_catalog.publish_audit_enrollment_urls,
            str(enterprise_catalog.enterprise_catalog_query.uuid),
            enterprise_catalog.enterprise_catalog_query.title,
            enterprise_catalog.enterprise_catalog_query.include_exec_ed_2u_courses,
        )
        api_client_mock.return_value.refresh_catalogs.assert_called_with([enterprise_catalog])

    @mock.patch('enterprise.signals.EnterpriseCatalogApiClient')
    def test_update_catalog_without_existing_service_catalog(self, api_client_mock):
        enterprise_catalog = EnterpriseCustomerCatalogFactory()
        api_client_mock.return_value.get_enterprise_catalog.return_value = {}

        enterprise_catalog.title = 'New title'
        enterprise_catalog.save()

        # Verify the API was called and the catalog is the same as there were no real updates
        api_client_mock.return_value.create_enterprise_catalog.assert_called_with(
            str(enterprise_catalog.uuid),
            str(enterprise_catalog.enterprise_customer.uuid),
            enterprise_catalog.enterprise_customer.name,
            enterprise_catalog.title,
            enterprise_catalog.content_filter,
            enterprise_catalog.enabled_course_modes,
            enterprise_catalog.publish_audit_enrollment_urls,
            str(enterprise_catalog.enterprise_catalog_query.uuid),
            enterprise_catalog.enterprise_catalog_query.title,
            enterprise_catalog.enterprise_catalog_query.include_exec_ed_2u_courses,
        )
        api_client_mock.return_value.refresh_catalogs.assert_called_with([enterprise_catalog])

    @mock.patch('enterprise.signals.EnterpriseCatalogApiClient')
    def test_update_catalog_with_existing_service_catalog(self, api_client_mock):
        enterprise_catalog = EnterpriseCustomerCatalogFactory()
        api_client_mock.return_value.get_enterprise_catalog.return_value = True

        enterprise_catalog.title = 'New title'
        enterprise_catalog.save()

        # Verify the API was called and the catalog is the same as there were no real updates
        api_client_mock.return_value.update_enterprise_catalog.assert_called_with(
            enterprise_catalog.uuid,
            enterprise_customer=str(enterprise_catalog.enterprise_customer.uuid),
            enterprise_customer_name=enterprise_catalog.enterprise_customer.name,
            title=enterprise_catalog.title,
            content_filter=enterprise_catalog.content_filter,
            enabled_course_modes=enterprise_catalog.enabled_course_modes,
            publish_audit_enrollment_urls=enterprise_catalog.publish_audit_enrollment_urls,
            catalog_query_uuid=str(enterprise_catalog.enterprise_catalog_query.uuid),
            query_title=enterprise_catalog.enterprise_catalog_query.title,
            include_exec_ed_2u_courses=enterprise_catalog.enterprise_catalog_query.include_exec_ed_2u_courses,
        )
        api_client_mock.return_value.refresh_catalogs.assert_called_with([enterprise_catalog])

    @mock.patch('enterprise.signals.EnterpriseCatalogApiClient')
    def test_update_enterprise_catalog_query(self, api_client_mock):
        """
        Tests the update_enterprise_query post_save signal.

        Creates an EnterpriseCatalogQuery instance and two separate EnterpriseCatalog
        instances that are associated with the query. The query's content filter is then
        updated to see if the changes are applied across both related catalogs. Additionally,
        there is a test to see if the sync is sent to the EnterpriseCatalogApi service
        which is done through the mock api client.
        """
        content_filter_1 = OrderedDict({
            'content_type': 'course1',
        })
        content_filter_2 = OrderedDict({
            'content_type': 'course2',
        })

        test_query = EnterpriseCatalogQueryFactory(
            content_filter=content_filter_1
        )
        enterprise_catalog_1 = EnterpriseCustomerCatalogFactory(
            enterprise_catalog_query=test_query
        )
        enterprise_catalog_2 = EnterpriseCustomerCatalogFactory(
            enterprise_catalog_query=test_query
        )

        test_query.content_filter = content_filter_2
        test_query.save()

        enterprise_catalog_1.refresh_from_db()
        enterprise_catalog_2.refresh_from_db()

        self.assertEqual(enterprise_catalog_1.content_filter, content_filter_2)
        self.assertEqual(enterprise_catalog_2.content_filter, content_filter_2)

        api_client_mock.return_value.get_enterprise_catalog.return_value = True

        # verify that the mock api was called when saving the catalog after updating the query
        # enterprise_catalog_2 was most recently modified so the last call should be for that
        api_client_mock.return_value.update_enterprise_catalog.assert_called_with(
            enterprise_catalog_2.uuid,
            enterprise_customer=str(enterprise_catalog_2.enterprise_customer.uuid),
            enterprise_customer_name=enterprise_catalog_2.enterprise_customer.name,
            title=enterprise_catalog_2.title,
            content_filter=enterprise_catalog_2.content_filter,
            enabled_course_modes=enterprise_catalog_2.enabled_course_modes,
            publish_audit_enrollment_urls=enterprise_catalog_2.publish_audit_enrollment_urls,
            catalog_query_uuid=str(test_query.uuid),
            query_title=test_query.title,
            include_exec_ed_2u_courses=test_query.include_exec_ed_2u_courses,
        )
        api_client_mock.return_value.refresh_catalogs.assert_called_with([enterprise_catalog_2])
