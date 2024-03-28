"""
Tests for the `edx-enterprise` tasks module.
"""

import copy
import unittest
import uuid
from datetime import datetime
from unittest import mock

from pytest import mark

from enterprise.constants import SSO_BRAZE_CAMPAIGN_ID
from enterprise.models import EnterpriseCourseEnrollment, EnterpriseEnrollmentSource
from enterprise.settings.test import BRAZE_GROUPS_INVITATION_EMAIL_CAMPAIGN_ID, BRAZE_GROUPS_REMOVAL_EMAIL_CAMPAIGN_ID
from enterprise.tasks import (
    create_enterprise_enrollment,
    send_enterprise_email_notification,
    send_group_membership_invitation_notification,
    send_group_membership_removal_notification,
    send_sso_configured_email,
)
from enterprise.utils import serialize_notification_content
from test_utils.factories import (
    EnterpriseCustomerFactory,
    EnterpriseCustomerUserFactory,
    EnterpriseGroupFactory,
    EnterpriseGroupMembershipFactory,
    PendingEnterpriseCustomerUserFactory,
    UserFactory,
)


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
        self.enterprise_group_memberships = []

        self.enterprise_group_memberships.append(EnterpriseGroupMembershipFactory(
            group=self.enterprise_group,
            pending_enterprise_customer_user=None,
            enterprise_customer_user__enterprise_customer=self.enterprise_customer,
        ))
        self.enterprise_group_memberships.append(EnterpriseGroupMembershipFactory(
            group=self.enterprise_group,
            pending_enterprise_customer_user=self.pending_enterprise_customer_user,
            enterprise_customer_user=None,
        ))
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
        admin_email = 'edx@example.org'
        mock_recipients = [{'external_user_id': 1}, self.pending_enterprise_customer_user.user_email]
        mock_catalog_content_count = 5
        mock_admin_mailto = f'mailto:{admin_email}'
        mock_braze_api_client().create_recipient.return_value = mock_recipients[0]
        mock_braze_api_client().generate_mailto_link.return_value = mock_admin_mailto
        mock_braze_api_client().create_recipient_no_external_id.return_value = (
            self.pending_enterprise_customer_user.user_email)
        mock_enterprise_catalog_client().get_catalog_content_count.return_value = (
            mock_catalog_content_count)
        budget_expiration = datetime.now()
        catalog_uuid = uuid.uuid4()
        for membership in self.enterprise_group_memberships:
            send_group_membership_invitation_notification(
                self.enterprise_customer.uuid,
                membership.uuid,
                budget_expiration,
                catalog_uuid,
            )
        calls = [mock.call(
            BRAZE_GROUPS_INVITATION_EMAIL_CAMPAIGN_ID,
            recipients=[recipient],
            trigger_properties={
                'contact_admin_link': mock_admin_mailto,
                'enterprise_customer_name': self.enterprise_customer.name,
                'catalog_content_count': mock_catalog_content_count,
                'budget_end_date': budget_expiration,
            },
        ) for recipient in mock_recipients]
        mock_braze_api_client().send_campaign_message.assert_has_calls(calls)

    @mock.patch('enterprise.tasks.EnterpriseCatalogApiClient', return_value=mock.MagicMock())
    @mock.patch('enterprise.tasks.BrazeAPIClient', return_value=mock.MagicMock())
    def test_send_group_membership_removal_notification(self, mock_braze_api_client, mock_enterprise_catalog_client):
        """
        Verify send_group_membership_removal_notification hits braze client with expected args
        """
        admin_email = 'edx@example.org'
        mock_recipients = [{'external_user_id': 1}, self.pending_enterprise_customer_user.user_email]
        mock_catalog_content_count = 5
        mock_admin_mailto = f'mailto:{admin_email}'
        mock_braze_api_client().create_recipient.return_value = mock_recipients[0]
        mock_braze_api_client().generate_mailto_link.return_value = mock_admin_mailto
        mock_braze_api_client().create_recipient_no_external_id.return_value = (
            self.pending_enterprise_customer_user.user_email)
        mock_enterprise_catalog_client().get_catalog_content_count.return_value = (
            mock_catalog_content_count)
        for membership in self.enterprise_group_memberships:
            send_group_membership_removal_notification(
                self.enterprise_customer.uuid,
                membership.uuid,
            )
        calls = [mock.call(
            BRAZE_GROUPS_REMOVAL_EMAIL_CAMPAIGN_ID,
            recipients=[recipient],
            trigger_properties={
                'contact_admin_link': mock_admin_mailto,
                'enterprise_customer_name': self.enterprise_customer.name,
            },
        ) for recipient in mock_recipients]
        mock_braze_api_client().send_campaign_message.assert_has_calls(calls)

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
