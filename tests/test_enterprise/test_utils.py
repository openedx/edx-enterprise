# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` utils module.
"""
import unittest
from unittest import mock

import ddt
from pytest import mark

from django.conf import settings

from enterprise.models import EnterpriseCourseEnrollment
from enterprise.utils import enroll_licensed_users_in_courses, get_idiff_list, get_platform_logo_url
from test_utils import FAKE_UUIDS, TEST_PASSWORD, TEST_USERNAME, factories


@mark.django_db
@ddt.ddt
class TestGetDifferenceList(unittest.TestCase):
    """
    Tests for :method:`get_idiff_list`.
    """

    @ddt.unpack
    @ddt.data(
        (
            [],
            [],
            []
        ),
        (
            ['DUMMY1@example.com', 'dummy2@example.com', 'dummy3@example.com'],
            ['dummy1@example.com', 'DUMMY3@EXAMPLE.COM'],
            ['dummy2@example.com']
        ),
        (
            ['dummy1@example.com', 'dummy2@example.com', 'dummy3@example.com'],
            [],
            ['dummy1@example.com', 'dummy2@example.com', 'dummy3@example.com'],
        )
    )
    def test_get_idiff_list_method(self, all_emails, registered_emails, unregistered_emails):
        emails = get_idiff_list(all_emails, registered_emails)
        self.assertEqual(sorted(emails), sorted(unregistered_emails))


@mark.django_db
@ddt.ddt
class TestUtils(unittest.TestCase):
    """
    Tests for utility functions in enterprise.utils
    """
    # pylint: disable=arguments-renamed

    def create_user(self, username=TEST_USERNAME, password=TEST_PASSWORD, is_staff=False, **kwargs):
        """
        Create a test user and set its password.
        """
        # pylint: disable=attribute-defined-outside-init
        self.user = factories.UserFactory(username=username, is_active=True, is_staff=is_staff, **kwargs)
        self.user.set_password(password)  # pylint: disable=no-member
        self.user.save()  # pylint: disable=no-member

    @ddt.unpack
    @ddt.data(
        (None, None),
        ('http://fake.url/logo.png', 'http://fake.url/logo.png'),
        ('./images/logo.png', '{}/images/logo.png'.format(settings.LMS_ROOT_URL)),
    )
    @mock.patch('enterprise.utils.get_logo_url')
    def test_get_platform_logo_url(self, logo_url, expected_logo_url, mock_get_logo_url):
        """
        Verify that the URL returned from get_logo_url is
        returned from get_platform_logo_url.
        """
        mock_get_logo_url.return_value = logo_url
        self.assertEqual(get_platform_logo_url(), expected_logo_url)

    @mock.patch('enterprise.utils.customer_admin_enroll_user')
    def test_enroll_licensed_users_in_courses_fails(self, mock_customer_admin_enroll_user):
        """
        Test that `enroll_licensed_users_in_courses` properly handles failure cases where something goes wrong with the
        user enrollment.
        """
        self.create_user()
        ent_customer = factories.EnterpriseCustomerFactory(
            uuid=FAKE_UUIDS[0],
            name="test_enterprise"
        )
        mock_customer_admin_enroll_user.return_value = False
        licensed_users_info = [{
            'email': self.user.email,
            'course_run_key': 'course-key-v1',
            'course_mode': 'verified',
            'license_uuid': '5b77bdbade7b4fcb838f8111b68e18ae'
        }]

        result = enroll_licensed_users_in_courses(ent_customer, licensed_users_info)
        self.assertEqual(
            {
                'successes': [],
                'failures': [{'email': self.user.email, 'course_run_key': 'course-key-v1'}],
                'pending': []
            },
            result
        )

    @mock.patch('enterprise.utils.customer_admin_enroll_user')
    def test_enroll_licensed_users_in_courses_fails_with_exception(self, mock_customer_admin_enroll_user):
        """
        Test that `enroll_licensed_users_in_courses` properly handles failure cases where badly formed data throws a
        database Integrity Error.
        """
        self.create_user()
        ent_customer = factories.EnterpriseCustomerFactory(
            uuid=FAKE_UUIDS[0],
            name="test_enterprise"
        )
        mock_customer_admin_enroll_user.return_value = True
        licensed_users_info = [{
            'email': self.user.email,
            'course_run_key': 'course-key-v1',
            'course_mode': 'verified',
            'license_uuid': '5b77bdbade7b4fcb838f8111b68e18ae'
        }]

        # Attempt to enroll a user that isn't associated with an enterprise, causing an integrity error.
        result = enroll_licensed_users_in_courses(ent_customer, licensed_users_info)
        self.assertEqual(
            {
                'successes': [],
                'pending': [],
                'failures': [{'email': self.user.email, 'course_run_key': 'course-key-v1'}]
            },
            result
        )

    @mock.patch('enterprise.utils.customer_admin_enroll_user')
    def test_enroll_licensed_users_in_courses_partially_fails(self, mock_customer_admin_enroll_user):
        """
        Test that `enroll_licensed_users_in_courses` properly handles partial failure states and still creates
        enrollments for the users that succeed.
        """
        self.create_user()
        failure_user = factories.UserFactory()

        ent_customer = factories.EnterpriseCustomerFactory(
            uuid=FAKE_UUIDS[0],
            name="test_enterprise"
        )
        factories.EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=ent_customer,
        )

        licensed_users_info = [
            {
                'email': self.user.email,
                'course_run_key': 'course-key-v1',
                'course_mode': 'verified',
                'license_uuid': '5b77bdbade7b4fcb838f8111b68e18ae'
            },
            {
                'email': failure_user.email,
                'course_run_key': 'course-key-v1',
                'course_mode': 'verified',
                'license_uuid': '5b77bdbade7b4fcb838f8111b68e18ae'
            }
        ]

        mock_customer_admin_enroll_user.return_value = True

        result = enroll_licensed_users_in_courses(ent_customer, licensed_users_info)
        self.assertEqual(
            {
                'pending': [],
                'successes': [{'email': self.user.email, 'course_run_key': 'course-key-v1', 'user': self.user}],
                'failures': [{'email': failure_user.email, 'course_run_key': 'course-key-v1'}]
            },
            result
        )
        self.assertEqual(len(EnterpriseCourseEnrollment.objects.all()), 1)

    @mock.patch('enterprise.utils.customer_admin_enroll_user')
    def test_enroll_licensed_users_in_courses_succeeds(self, mock_customer_admin_enroll_user):
        """
        Test that users that already exist are enrolled by enroll_licensed_users_in_courses and returned under the
        `succeeded` field.
        """
        self.create_user()

        ent_customer = factories.EnterpriseCustomerFactory(
            uuid=FAKE_UUIDS[0],
            name="test_enterprise"
        )
        factories.EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=ent_customer,
        )
        licensed_users_info = [{
            'email': self.user.email,
            'course_run_key': 'course-key-v1',
            'course_mode': 'verified',
            'license_uuid': '5b77bdbade7b4fcb838f8111b68e18ae'
        }]

        mock_customer_admin_enroll_user.return_value = True

        result = enroll_licensed_users_in_courses(ent_customer, licensed_users_info)
        self.assertEqual(
            {
                'pending': [],
                'successes': [{'email': self.user.email, 'course_run_key': 'course-key-v1', 'user': self.user}],
                'failures': []
            },
            result
        )
        self.assertEqual(len(EnterpriseCourseEnrollment.objects.all()), 1)

    def test_enroll_pending_licensed_users_in_courses_succeeds(self):
        """
        Test that users that do not exist are pre-enrolled by enroll_licensed_users_in_courses and returned under the
        `pending` field.
        """
        ent_customer = factories.EnterpriseCustomerFactory(
            uuid=FAKE_UUIDS[0],
            name="test_enterprise"
        )
        licensed_users_info = [{
            'email': 'pending-user-email@example.com',
            'course_run_key': 'course-key-v1',
            'course_mode': 'verified',
            'license_uuid': '5b77bdbade7b4fcb838f8111b68e18ae'
        }]
        result = enroll_licensed_users_in_courses(ent_customer, licensed_users_info)

        self.assertEqual(result['pending'][0]['email'], 'pending-user-email@example.com')
        self.assertFalse(result['successes'])
        self.assertFalse(result['failures'])
