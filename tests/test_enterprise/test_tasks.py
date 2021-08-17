# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` tasks module.
"""

import copy
import unittest

import mock
from pytest import mark

from enterprise.models import EnterpriseCourseEnrollment, EnterpriseEnrollmentSource
from enterprise.tasks import create_enterprise_enrollment, send_enterprise_email_notification
from enterprise.utils import serialize_notification_content
from test_utils.factories import (
    EnterpriseCustomerFactory,
    EnterpriseCustomerUserFactory,
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
        self.user = UserFactory(id=2, email='user@example.com')
        self.enterprise_customer = EnterpriseCustomerFactory(
            name='Team Titans',
        )
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
