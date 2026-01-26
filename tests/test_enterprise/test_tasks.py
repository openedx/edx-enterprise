"""
Tests for the `edx-enterprise` tasks module.
"""

import copy
import unittest
import uuid
from datetime import datetime
from unittest import mock

import ddt
from pytest import mark, raises

from enterprise.api_client.braze import ENTERPRISE_BRAZE_ALIAS_LABEL
from enterprise.constants import SSO_BRAZE_CAMPAIGN_ID
from enterprise.models import EnterpriseCourseEnrollment, EnterpriseEnrollmentSource, EnterpriseGroupMembership
from enterprise.settings.test import BRAZE_GROUPS_INVITATION_EMAIL_CAMPAIGN_ID, BRAZE_GROUPS_REMOVAL_EMAIL_CAMPAIGN_ID
from enterprise.tasks import (
    create_enterprise_enrollment,
    send_enterprise_email_notification,
    send_group_membership_invitation_notification,
    send_group_membership_removal_notification,
    send_sso_configured_email,
    track_enterprise_language_update_for_all_learners,
)
from enterprise.utils import localized_utcnow, serialize_notification_content
from test_utils.factories import (
    EnterpriseCustomerFactory,
    EnterpriseCustomerUserFactory,
    EnterpriseGroupFactory,
    EnterpriseGroupMembershipFactory,
    PendingEnterpriseCustomerUserFactory,
    UserFactory,
)

try:
    from braze.exceptions import BrazeClientError
except ImportError:
    BrazeClientError = Exception


@mark.django_db
class TestEnterpriseTasks(unittest.TestCase):
    """
    Tests tasks associated with Enterprise.
    """
    FAKE_COURSE_ID = 'course-v1:edx+Test+2T2019'

    def setUp(self):
        """
        Setup for `TestEnterpriseTasks` test.
        """
        self.enterprise_customer = EnterpriseCustomerFactory(
            name='Team Titans',
        )
        self.user = UserFactory(email='user@example.com')
        self.pending_enterprise_customer_user = PendingEnterpriseCustomerUserFactory()
        self.enterprise_group = EnterpriseGroupFactory(enterprise_customer=self.enterprise_customer)
        self.enterprise_customer_user = EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=self.enterprise_customer,
        )
        super().setUp()

    @mock.patch('enterprise.models.EnterpriseCustomer.catalog_contains_course')
    def test_create_enrollment_task_course_in_catalog(self, mock_contains_course):
        """
        Task should create an enterprise enrollment if the course_id handed to
        the function is part of the EnterpriseCustomer's catalogs
        """
        mock_contains_course.return_value = True
        assert EnterpriseCourseEnrollment.objects.count() == 0
        create_enterprise_enrollment(
            self.FAKE_COURSE_ID,
            self.enterprise_customer_user.id
        )
        assert EnterpriseCourseEnrollment.objects.count() == 1

    @mock.patch('enterprise.models.EnterpriseCustomer.catalog_contains_course')
    def test_create_enrollment_task_source_set(self, mock_contains_course):
        """
        Task should create an enterprise enrollment if the course_id handed to
        the function is part of the EnterpriseCustomer's catalogs
        """
        mock_contains_course.return_value = True
        assert EnterpriseCourseEnrollment.objects.count() == 0
        create_enterprise_enrollment(
            self.FAKE_COURSE_ID,
            self.enterprise_customer_user.id
        )
        assert EnterpriseCourseEnrollment.objects.count() == 1
        assert EnterpriseCourseEnrollment.objects.get(
            course_id=self.FAKE_COURSE_ID,
        ).source.slug == EnterpriseEnrollmentSource.ENROLLMENT_TASK

    @mock.patch('enterprise.models.EnterpriseCustomer.catalog_contains_course')
    def test_create_enrollment_task_course_not_in_catalog(self, mock_contains_course):
        """
        Task should NOT create an enterprise enrollment if the course_id handed
        to the function is NOT part of the EnterpriseCustomer's catalogs
        """
        mock_contains_course.return_value = False

        assert EnterpriseCourseEnrollment.objects.count() == 0
        create_enterprise_enrollment(
            self.FAKE_COURSE_ID,
            self.enterprise_customer_user.id
        )
        assert EnterpriseCourseEnrollment.objects.count() == 0

    @mock.patch('enterprise.models.EnterpriseCatalogApiClient')
    def test_create_enrollment_task_no_create_duplicates(self, catalog_api_client_mock):
        """
        Task should return without creating a new EnterpriseCourseEnrollment
        if one with the course_id and enterprise_customer_user specified
        already exists.
        """
        EnterpriseCourseEnrollment.objects.create(
            course_id=self.FAKE_COURSE_ID,
            enterprise_customer_user=self.enterprise_customer_user,
        )
        catalog_api_client_mock.return_value.contains_content_items.return_value = False

        assert EnterpriseCourseEnrollment.objects.count() == 1
        create_enterprise_enrollment(
            self.FAKE_COURSE_ID,
            self.enterprise_customer_user.id
        )
        assert EnterpriseCourseEnrollment.objects.count() == 1

    @mock.patch('enterprise.tasks.mail.get_connection')
    @mock.patch('enterprise.tasks.send_email_notification_message')
    def test_enterprise_email_notification_failsafe(self, mock_send_notification, mock_email_conn):
        """
        Verify one failure does not interrupt emails for all learners
        """
        enterprise_customer = EnterpriseCustomerFactory()

        mock_send_notification.side_effect = Exception("Any thing that happens during email")

        mail_conn = mock.MagicMock()
        mock_email_conn.return_value.__enter__.return_value = mail_conn

        item1 = {
            "user": {'username': 'test'},
            "enrolled_in": {
                "name": "test_course",
                "url": "https://test/url",
                "type": "course",
                "start": "2021-01-01T00:10:10",
            },
            "dashboard_url": "https://test/url",
            "enterprise_customer_uuid": enterprise_customer.uuid,
            "admin_enrollment": True,
        }
        item2 = copy.copy(item1)
        item2["user"]["user_email"] = "abc@test.com"

        email_items = [item1, item2]

        # check exception is logged at ERROR level twice, in this case
        # but causes no failures otherwise
        with self.assertLogs('enterprise.tasks', level='ERROR') as log_cm:
            send_enterprise_email_notification(
                enterprise_customer.uuid,
                True,
                email_items,
            )
            self.assertEqual(2, len(log_cm.records))
        mock_email_conn.assert_called_once()

    @mock.patch('enterprise.tasks.mail.get_connection')
    @mock.patch('enterprise.tasks.send_email_notification_message')
    def test_send_enterprise_email_notification(self, mock_send_notification, mock_email_conn):
        enterprise_customer = EnterpriseCustomerFactory()
        pending_user = PendingEnterpriseCustomerUserFactory()
        users = [UserFactory(username=f'user{user_id}') for user_id in range(1, 10)]
        course_details = {'title': 'course_title', 'start': '2021-09-21T00:01:10'}
        admin_enrollment = True

        mail_conn = mock.MagicMock()
        mock_email_conn.return_value.__enter__.return_value = mail_conn

        email_items = serialize_notification_content(
            enterprise_customer,
            course_details,
            self.FAKE_COURSE_ID,
            users + [pending_user],
            admin_enrollment,
        )
        send_enterprise_email_notification(
            enterprise_customer.uuid,
            admin_enrollment,
            email_items,
        )
        calls = [mock.call(
            item['user'],
            item['enrolled_in'],
            item['dashboard_url'],
            enterprise_customer.uuid,
            email_connection=mail_conn,
            admin_enrollment=admin_enrollment,
        ) for item in email_items]
        mock_send_notification.assert_has_calls(calls)

    @mock.patch('enterprise.tasks.EnterpriseCatalogApiClient', return_value=mock.MagicMock())
    @mock.patch('enterprise.tasks.BrazeAPIClient', return_value=mock.MagicMock())
    def test_send_group_membership_invitation_notification(self, mock_braze_api_client, mock_enterprise_catalog_client):
        """
        Verify send_group_membership_invitation_notification hits braze client with expected args
        """
        EnterpriseGroupMembershipFactory(
            group=self.enterprise_group,
            pending_enterprise_customer_user=self.pending_enterprise_customer_user,
            enterprise_customer_user=None,
        )
        EnterpriseGroupMembershipFactory(
            group=self.enterprise_group,
            pending_enterprise_customer_user=None,
            enterprise_customer_user__enterprise_customer=self.enterprise_customer,
            activated_at=datetime.now()
        )
        admin_email = 'edx@example.org'
        mock_braze_api_client().create_recipients.return_value = {
            self.user.email: {
                "external_user_id": self.user.id,
                "attributes": {
                    "user_alias": {
                        "external_id": self.user.id,
                        "user_alias": self.user.email,
                    },
                }
            }
        }
        mock_recipients = [
            self.pending_enterprise_customer_user.user_email,
            {
                "external_user_id": self.user.id,
                "attributes": {
                    "user_alias": {
                        "external_id": self.user.id,
                        "user_alias": self.user.email,
                    },
                }
            }
        ]
        mock_catalog_content_count = 5
        mock_admin_mailto = f'mailto:{admin_email}'
        mock_braze_api_client().generate_mailto_link.return_value = mock_admin_mailto
        mock_braze_api_client().create_recipient_no_external_id.return_value = (
            self.pending_enterprise_customer_user.user_email)
        mock_enterprise_catalog_client().get_catalog_content_count.return_value = (
            mock_catalog_content_count)
        act_by_date = datetime.today()
        catalog_uuid = uuid.uuid4()
        membership_uuids = EnterpriseGroupMembership.objects.values_list('uuid', flat=True)
        send_group_membership_invitation_notification(
            self.enterprise_customer.uuid,
            membership_uuids,
            act_by_date,
            catalog_uuid,
        )
        calls = [mock.call(
            BRAZE_GROUPS_INVITATION_EMAIL_CAMPAIGN_ID,
            recipients=mock_recipients,
            trigger_properties={
                'contact_admin_link': mock_admin_mailto,
                'enterprise_customer_name': self.enterprise_customer.name,
                'catalog_content_count': mock_catalog_content_count,
                'act_by_date': act_by_date.strftime('%B %d, %Y'),
            },
        )]
        mock_braze_api_client().send_campaign_message.assert_has_calls(calls)
        mock_braze_api_client().create_braze_alias.assert_called_once_with(
            [self.pending_enterprise_customer_user.user_email], ENTERPRISE_BRAZE_ALIAS_LABEL)

    @mock.patch('enterprise.tasks.EnterpriseCatalogApiClient', return_value=mock.MagicMock())
    @mock.patch('enterprise.tasks.BrazeAPIClient', return_value=mock.MagicMock())
    def test_fail_send_group_membership_invitation_notification(
        self,
        mock_braze_api_client,
        mock_enterprise_catalog_client,
    ):
        """
        Verify failed send group invitation email
        """
        pending_membership = EnterpriseGroupMembershipFactory(
            group=self.enterprise_group,
            pending_enterprise_customer_user=self.pending_enterprise_customer_user,
            enterprise_customer_user=None,
        )
        admin_email = 'edx@example.org'
        mock_braze_api_client().create_recipients.return_value = {
            self.user.email: {
                "external_user_id": self.user.id,
                "attributes": {
                    "user_alias": {
                        "external_id": self.user.id,
                        "user_alias": self.user.email,
                    },
                }
            }
        }

        mock_catalog_content_count = 5
        mock_admin_mailto = f'mailto:{admin_email}'
        mock_braze_api_client().generate_mailto_link.return_value = mock_admin_mailto
        mock_braze_api_client().create_recipient_no_external_id.return_value = (
            self.pending_enterprise_customer_user.user_email)
        mock_enterprise_catalog_client().get_catalog_content_count.return_value = (
            mock_catalog_content_count)
        act_by_date = datetime.today()
        catalog_uuid = uuid.uuid4()
        membership_uuids = EnterpriseGroupMembership.objects.values_list('uuid', flat=True)
        mock_braze_api_client().send_campaign_message.side_effect = BrazeClientError(
            "Any thing that happens during email")
        errored_at = localized_utcnow()
        with raises(BrazeClientError):
            send_group_membership_invitation_notification(
                self.enterprise_customer.uuid,
                membership_uuids,
                act_by_date,
                catalog_uuid)
            pending_membership.refresh_from_db()
            assert pending_membership.status == 'email_error'
            assert pending_membership.errored_at == errored_at
            assert pending_membership.recent_action == f"Errored: {errored_at.strftime('%B %d, %Y')}"

    @mock.patch('enterprise.tasks.EnterpriseCatalogApiClient', return_value=mock.MagicMock())
    @mock.patch('enterprise.tasks.BrazeAPIClient', return_value=mock.MagicMock())
    def test_send_group_membership_removal_notification(self, mock_braze_api_client, mock_enterprise_catalog_client):
        """
        Verify send_group_membership_removal_notification hits braze client with expected args
        """
        pecu_membership = EnterpriseGroupMembershipFactory(
            group=self.enterprise_group,
            pending_enterprise_customer_user=self.pending_enterprise_customer_user,
            enterprise_customer_user=None,
        )
        ecu_membership = EnterpriseGroupMembershipFactory(
            group=self.enterprise_group,
            pending_enterprise_customer_user=None,
            enterprise_customer_user__enterprise_customer=self.enterprise_customer,
            activated_at=datetime.now()
        )
        pecu_membership.delete()
        ecu_membership.delete()
        admin_email = 'edx@example.org'
        mock_braze_api_client().create_recipients.return_value = {
            self.user.email: {
                "external_user_id": self.user.id,
                "attributes": {
                    "user_alias": {
                        "external_id": self.user.id,
                        "user_alias": self.user.email,
                    },
                }
            }
        }
        mock_recipients = [
            self.pending_enterprise_customer_user.user_email,
            {
                "external_user_id": self.user.id,
                "attributes": {
                    "user_alias": {
                        "external_id": self.user.id,
                        "user_alias": self.user.email,
                    },
                }
            }
        ]
        mock_admin_mailto = f'mailto:{admin_email}'
        mock_braze_api_client().generate_mailto_link.return_value = mock_admin_mailto
        mock_braze_api_client().create_recipient_no_external_id.return_value = (
            self.pending_enterprise_customer_user.user_email)
        mock_catalog_content_count = 5
        mock_enterprise_catalog_client().get_catalog_content_count.return_value = (
            mock_catalog_content_count)
        membership_uuids = EnterpriseGroupMembership.all_objects.values_list('uuid', flat=True)
        catalog_uuid = uuid.uuid4()
        send_group_membership_removal_notification(
            self.enterprise_customer.uuid,
            membership_uuids,
            catalog_uuid,
        )
        calls = [mock.call(
            BRAZE_GROUPS_REMOVAL_EMAIL_CAMPAIGN_ID,
            recipients=mock_recipients,
            trigger_properties={
                'contact_admin_link': mock_admin_mailto,
                'enterprise_customer_name': self.enterprise_customer.name,
                'catalog_content_count': mock_catalog_content_count,
            },
        )]

        mock_braze_api_client().create_braze_alias.assert_called_once_with(
            [self.pending_enterprise_customer_user.user_email], ENTERPRISE_BRAZE_ALIAS_LABEL)
        mock_braze_api_client().send_campaign_message.assert_has_calls(calls)

    @mock.patch('enterprise.tasks.EnterpriseCatalogApiClient', return_value=mock.MagicMock())
    @mock.patch('enterprise.tasks.BrazeAPIClient', return_value=mock.MagicMock())
    def test_fail_send_group_membership_removal_notification(
        self,
        mock_braze_api_client,
        mock_enterprise_catalog_client,
    ):
        """
        Verify failed send group removal email
        """
        pending_membership = EnterpriseGroupMembershipFactory(
            group=self.enterprise_group,
            pending_enterprise_customer_user=self.pending_enterprise_customer_user,
            enterprise_customer_user=None,
        )
        admin_email = 'edx@example.org'
        mock_braze_api_client().create_recipients.return_value = {
            self.user.email: {
                "external_user_id": self.user.id,
                "attributes": {
                    "user_alias": {
                        "external_id": self.user.id,
                        "user_alias": self.user.email,
                    },
                }
            }
        }

        mock_catalog_content_count = 5
        mock_admin_mailto = f'mailto:{admin_email}'
        mock_braze_api_client().generate_mailto_link.return_value = mock_admin_mailto
        mock_braze_api_client().create_recipient_no_external_id.return_value = (
            self.pending_enterprise_customer_user.user_email)
        mock_enterprise_catalog_client().get_catalog_content_count.return_value = (
            mock_catalog_content_count)
        catalog_uuid = uuid.uuid4()
        membership_uuids = EnterpriseGroupMembership.objects.values_list('uuid', flat=True)
        mock_braze_api_client().send_campaign_message.side_effect = BrazeClientError(
            "Any thing that happens during email")
        errored_at = localized_utcnow()
        with raises(BrazeClientError):
            send_group_membership_removal_notification(
                self.enterprise_customer.uuid,
                membership_uuids,
                catalog_uuid)
            pending_membership.refresh_from_db()
            assert pending_membership.status == 'email_error'
            assert pending_membership.errored_at == localized_utcnow()
            assert pending_membership.recent_action == f"Errored: {errored_at.strftime('%B %d, %Y')}"

    @mock.patch('enterprise.tasks.BrazeAPIClient', return_value=mock.MagicMock())
    def test_sso_configuration_oauth_orchestration_email(self, mock_braze_client):
        """
        Assert sso configuration calls Braze API with the correct arguments.
        """
        mock_braze_client().create_recipient_no_external_id.return_value = (
            self.enterprise_customer.contact_email)
        expected_trigger_properties = {
            'enterprise_customer_slug': self.enterprise_customer.slug,
            'enterprise_customer_name': self.enterprise_customer.name,
            'enterprise_sender_alias': self.enterprise_customer.sender_alias,
            'enterprise_contact_email': self.enterprise_customer.contact_email,
        }
        send_sso_configured_email(self.enterprise_customer.uuid)
        call = [mock.call(
            SSO_BRAZE_CAMPAIGN_ID,
            recipients=[self.enterprise_customer.contact_email],
            trigger_properties=expected_trigger_properties
        )]
        mock_braze_client().send_campaign_message.assert_has_calls(call)


@mark.django_db
@ddt.ddt
class TestTrackEnterpriseLanguageUpdateForAllLearners(unittest.TestCase):
    """
    Tests for track_enterprise_language_update_for_all_learners task.
    """

    def setUp(self):
        """
        Setup for test.
        """
        self.enterprise_customer = EnterpriseCustomerFactory(
            name='Test Enterprise',
            default_language='en',
        )
        # Create active linked users
        self.active_users = [
            EnterpriseCustomerUserFactory(
                enterprise_customer=self.enterprise_customer,
                active=True,
                linked=True,
            )
            for _ in range(5)
        ]
        # Create inactive user (should be excluded)
        self.inactive_user = EnterpriseCustomerUserFactory(
            enterprise_customer=self.enterprise_customer,
            active=False,
            linked=True,
        )
        # Create unlinked user (should be excluded)
        self.unlinked_user = EnterpriseCustomerUserFactory(
            enterprise_customer=self.enterprise_customer,
            active=True,
            linked=False,
        )
        super().setUp()

    @ddt.data('es', None, 'fr', 'zh-cn')
    @mock.patch('enterprise.tasks.BrazeAPIClient')
    def test_track_language_update_success(self, new_language, mock_braze_client_class):
        """
        Verify task successfully tracks language update for all active linked users.
        Also verifies that inactive and unlinked users are excluded from processing.
        Tests with various language values including None.
        """
        mock_braze_instance = mock.MagicMock()
        mock_braze_client_class.return_value = mock_braze_instance

        track_enterprise_language_update_for_all_learners(
            str(self.enterprise_customer.uuid),
            new_language
        )

        # Verify track_user was called once (5 users fit in one batch of 75)
        assert mock_braze_instance.track_user.call_count == 1

        # Verify the attributes sent to Braze
        call_args = mock_braze_instance.track_user.call_args
        attributes = call_args[1]['attributes']

        # Should only include active, linked users (5 users, not 7)
        assert len(attributes) == 5

        # Verify each attribute has correct structure
        user_ids = [user.user_id for user in self.active_users]
        sent_user_ids = []
        for attr in attributes:
            assert attr['external_id'] in [str(uid) for uid in user_ids]
            assert attr['pref-lang'] == new_language
            sent_user_ids.append(attr['external_id'])

        # Verify inactive and unlinked users are excluded
        assert str(self.inactive_user.user_id) not in sent_user_ids
        assert str(self.unlinked_user.user_id) not in sent_user_ids

    @mock.patch('enterprise.tasks.BrazeAPIClient')
    def test_track_language_update_batching(self, mock_braze_client_class):
        """
        Verify task properly batches users when count exceeds batch size.
        """
        mock_braze_instance = mock.MagicMock()
        mock_braze_client_class.return_value = mock_braze_instance

        # Create 150 active linked users to test batching (75 per batch)
        for _ in range(145):  # 5 already exist from setUp
            EnterpriseCustomerUserFactory(
                enterprise_customer=self.enterprise_customer,
                active=True,
                linked=True,
            )

        track_enterprise_language_update_for_all_learners(
            str(self.enterprise_customer.uuid),
            'fr'
        )

        # Should be called twice: first batch of 75, second batch of 75
        assert mock_braze_instance.track_user.call_count == 2

        # Verify first batch has 75 users
        first_call_attributes = mock_braze_instance.track_user.call_args_list[0][1]['attributes']
        assert len(first_call_attributes) == 75

        # Verify second batch has remaining 75 users
        second_call_attributes = mock_braze_instance.track_user.call_args_list[1][1]['attributes']
        assert len(second_call_attributes) == 75

    @mock.patch('enterprise.tasks.BrazeAPIClient')
    def test_track_language_update_no_active_users(self, mock_braze_client_class):
        """
        Verify task exits early when no active users exist.
        """
        mock_braze_instance = mock.MagicMock()
        mock_braze_client_class.return_value = mock_braze_instance

        # Create enterprise with no active linked users
        empty_enterprise = EnterpriseCustomerFactory(name='Empty Enterprise')

        track_enterprise_language_update_for_all_learners(
            str(empty_enterprise.uuid),
            'de'
        )

        # Should not call track_user at all
        assert mock_braze_instance.track_user.call_count == 0
