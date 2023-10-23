"""
Tests for the `edx-enterprise` utils module.
"""
import unittest
from datetime import timedelta
from unittest import mock
from urllib.parse import quote, urlencode

import ddt
from pytest import mark

from django.conf import settings
from django.forms.models import model_to_dict

from enterprise.models import EnterpriseCourseEnrollment, LicensedEnterpriseCourseEnrollment
from enterprise.utils import (
    enroll_subsidy_users_in_courses,
    get_default_invite_key_expiration_date,
    get_idiff_list,
    get_platform_logo_url,
    is_pending_user,
    localized_utcnow,
    parse_lms_api_datetime,
    serialize_notification_content,
    truncate_string,
)
from enterprise.constants import MAX_ALLOWED_TEXT_LENGTH
from test_utils import FAKE_UUIDS, TEST_PASSWORD, TEST_USERNAME, factories

LMS_BASE_URL = 'https://lms.base.url'


class StubException(Exception):
    pass


class StubModel(Exception):
    pass


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

    def create_user(self, username=TEST_USERNAME, password=TEST_PASSWORD, is_staff=False, **kwargs):
        """
        Create a test user and set its password.
        """
        # pylint: disable=attribute-defined-outside-init
        self.user = factories.UserFactory(username=username, is_active=True, is_staff=is_staff, **kwargs)
        self.user.set_password(password)
        self.user.save()

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

    @mock.patch('enterprise.utils.CourseEnrollmentError', new_callable=lambda: StubException)
    @mock.patch('enterprise.utils.CourseUserGroup', new_callable=lambda: StubModel)
    @mock.patch('enterprise.utils.lms_update_or_create_enrollment')
    def test_enroll_subsidy_users_in_courses_fails(
        self,
        mock_update_or_create_enrollment,
        mock_model,
        mock_error,
    ):
        """
        Test that `enroll_subsidy_users_in_courses` properly handles failure cases where something goes wrong with the
        user enrollment.
        """
        self.create_user()
        ent_customer = factories.EnterpriseCustomerFactory(
            uuid=FAKE_UUIDS[0],
            name="test_enterprise"
        )
        mock_model.DoesNotExist = Exception
        mock_update_or_create_enrollment.side_effect = [mock_error('mocked error')]
        licensed_users_info = [{
            'email': self.user.email,
            'course_run_key': 'course-key-v1',
            'course_mode': 'verified',
            'license_uuid': '5b77bdbade7b4fcb838f8111b68e18ae'
        }]
        result = enroll_subsidy_users_in_courses(ent_customer, licensed_users_info)
        self.assertEqual(
            {
                "successes": [],
                "failures": [
                    {
                        "user_id": self.user.id,
                        "email": self.user.email,
                        "course_run_key": "course-key-v1",
                    }
                ],
                "pending": [],
            },
            result,
        )

    @mock.patch('enterprise.utils.CourseEnrollmentError', new_callable=lambda: StubException)
    @mock.patch('enterprise.utils.CourseUserGroup', new_callable=lambda: StubModel)
    @mock.patch('enterprise.utils.lms_update_or_create_enrollment')
    def test_enroll_subsidy_users_in_courses_partially_fails(
        self,
        mock_update_or_create_enrollment,
        mock_model,
        mock_error,
    ):
        """
        Test that `enroll_subsidy_users_in_courses` properly handles partial failure states and still creates
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
        mock_model.DoesNotExist = Exception
        mock_update_or_create_enrollment.side_effect = [True, mock_error('mocked error'), None]
        result = enroll_subsidy_users_in_courses(ent_customer, licensed_users_info)
        self.assertEqual(
            {
                'pending': [],
                'successes': [{
                    'user_id': self.user.id,
                    'email': self.user.email,
                    'course_run_key': 'course-key-v1',
                    'user': self.user,
                    'created': True,
                    'activation_link': None,
                    'enterprise_fulfillment_source_uuid': LicensedEnterpriseCourseEnrollment.objects.first().uuid,
                }],
                'failures': [{
                    'user_id': failure_user.id,
                    'email': failure_user.email,
                    'course_run_key': 'course-key-v1',
                }],
            },
            result
        )
        self.assertEqual(len(EnterpriseCourseEnrollment.objects.all()), 1)

    @mock.patch('enterprise.utils.lms_update_or_create_enrollment')
    def test_enroll_subsidy_users_in_courses_succeeds(
        self,
        mock_update_or_create_enrollment,
    ):
        """
        Test that users that already exist are enrolled by enroll_subsidy_users_in_courses and returned under the
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

        mock_update_or_create_enrollment.return_value = True
        result = enroll_subsidy_users_in_courses(ent_customer, licensed_users_info)
        self.assertEqual(
            {
                'pending': [],
                'successes': [{
                    'user_id': self.user.id,
                    'email': self.user.email,
                    'course_run_key': 'course-key-v1',
                    'user': self.user,
                    'created': True,
                    'activation_link': None,
                    'enterprise_fulfillment_source_uuid': LicensedEnterpriseCourseEnrollment.objects.first().uuid,
                }],
                'failures': []
            },
            result
        )
        self.assertEqual(len(EnterpriseCourseEnrollment.objects.all()), 1)

    @mock.patch('enterprise.utils.lms_update_or_create_enrollment')
    def test_enroll_subsidy_users_in_courses_with_user_id_succeeds(
        self,
        mock_update_or_create_enrollment,
    ):
        """
        Test that users that already exist are enrolled by enroll_subsidy_users_in_courses and returned under the
        ``succeeded`` field.  Specifically test when a ``user_id`` is supplied.
        """
        self.create_user()
        another_user = factories.UserFactory(is_active=True)

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
                # Should succeed with only a user_id supplied.
                'user_id': self.user.id,
                'course_run_key': 'course-key-1',
                'course_mode': 'verified',
                'license_uuid': '5b77bdbade7b4fcb838f8111b68e18ae',
            },
            {
                # Should succeed even with both a user_id and email supplied.
                'user_id': another_user.id,
                'email': another_user.email,
                'course_run_key': 'course-key-2',
                'course_mode': 'verified',
                'license_uuid': '5b77bdbade7b4fcb838f8111b68e18ae',
            },
        ]

        mock_update_or_create_enrollment.return_value = True

        result = enroll_subsidy_users_in_courses(ent_customer, licensed_users_info)
        self.assertEqual(
            {
                'pending': [],
                'successes': [
                    {
                        'user_id': self.user.id,
                        'email': self.user.email,
                        'course_run_key': 'course-key-1',
                        'user': self.user,
                        'created': True,
                        'activation_link': None,
                        'enterprise_fulfillment_source_uuid': EnterpriseCourseEnrollment.objects.filter(
                            enterprise_customer_user__user_id=self.user.id
                        ).first().licensedenterprisecourseenrollment_enrollment_fulfillment.uuid,
                    },
                    {
                        'user_id': another_user.id,
                        'email': another_user.email,
                        'course_run_key': 'course-key-2',
                        'user': another_user,
                        'created': True,
                        'activation_link': None,
                        'enterprise_fulfillment_source_uuid': EnterpriseCourseEnrollment.objects.filter(
                            enterprise_customer_user__user_id=another_user.id
                        ).first().licensedenterprisecourseenrollment_enrollment_fulfillment.uuid,
                    }
                ],
                'failures': [],
            },
            result
        )
        self.assertEqual(len(EnterpriseCourseEnrollment.objects.all()), 2)

    @mock.patch('enterprise.utils.lms_update_or_create_enrollment')
    def test_enroll_subsidy_users_in_courses_user_identifier_failures(
        self,
        mock_update_or_create_enrollment,

    ):
        """
        """
        self.create_user()
        another_user = factories.UserFactory(is_active=True)

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
                # Should fail due to the user_id not matching the email of the same user.
                'user_id': self.user.id,
                'email': another_user.email,
                'course_run_key': 'course-key-1',
                'course_mode': 'verified',
                'license_uuid': '5b77bdbade7b4fcb838f8111b68e18ae',
            },
            {
                # Should fail due to the user_id not matching the email of the same user.  Special case where the
                # user_id does not exist.
                'user_id': self.user.id + 1000,
                'email': self.user.email,
                'course_run_key': 'course-key-2',
                'course_mode': 'verified',
                'license_uuid': '5b77bdbade7b4fcb838f8111b68e18ae',
            },
            {
                # Should fail due to the user_id not matching the email of the same user.  Special case where the
                # email does not exist.
                'user_id': self.user.id,
                'email': 'wrong+' + self.user.email,
                'course_run_key': 'course-key-3',
                'course_mode': 'verified',
                'license_uuid': '5b77bdbade7b4fcb838f8111b68e18ae',
            },
            {
                # Should fail due to providing neither `user_id` nor `email`.
                'course_run_key': 'course-key-4',
                'course_mode': 'verified',
                'license_uuid': '5b77bdbade7b4fcb838f8111b68e18ae',
            },
        ]

        mock_update_or_create_enrollment.return_value = True

        result = enroll_subsidy_users_in_courses(ent_customer, licensed_users_info)
        self.assertEqual(
            {
                'pending': [],
                'successes': [],
                'failures': [
                    {
                        'user_id': self.user.id,
                        'email': another_user.email,
                        'course_run_key': 'course-key-1',
                    },
                    {
                        'user_id': self.user.id + 1000,
                        'email': self.user.email,
                        'course_run_key': 'course-key-2',
                    },
                    {
                        'user_id': self.user.id,
                        'email': 'wrong+' + self.user.email,
                        'course_run_key': 'course-key-3',
                    },
                    {
                        'course_run_key': 'course-key-4',
                    },
                ],
            },
            result
        )
        self.assertEqual(len(EnterpriseCourseEnrollment.objects.all()), 0)

    def test_enroll_pending_licensed_users_in_courses_succeeds(self):
        """
        Test that users that do not exist are pre-enrolled by enroll_subsidy_users_in_courses and returned under the
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
        result = enroll_subsidy_users_in_courses(ent_customer, licensed_users_info)

        self.assertEqual(result['pending'][0]['email'], 'pending-user-email@example.com')
        self.assertFalse(result['successes'])
        self.assertFalse(result['failures'])

    def setup_notification_test_data(self):
        """
        Creates data needed for testing serialization of email notifications data
        """
        ent_customer = factories.EnterpriseCustomerFactory(
            uuid=FAKE_UUIDS[0],
            name="test_enterprise"
        )
        user = factories.UserFactory()
        pending_user = factories.PendingEnterpriseCustomerUserFactory()
        needs_activation_user = factories.UserFactory()
        users = [user, pending_user, needs_activation_user]
        activation_links = {needs_activation_user.email: 'http://activation.test.learner.portal'}

        course_id = 'course-v1:edx+123+T2021'
        course_details = {'title': 'a_course', 'start': '2021-01-01T00:10:10', 'course': 'edx+123'}
        return ent_customer, users, course_id, course_details, activation_links

    @ddt.unpack
    @ddt.data(
        (True, 'http://test.learner.portal'),
        (False, None),
    )
    @mock.patch("enterprise.utils.get_configuration_value_for_site")
    @mock.patch("enterprise.utils.get_learner_portal_url")
    def test_serialize_notification_content(
        self,
        admin_enrollment,
        exp_dashboard_url,
        mock_get_learner_portal_url,
        mock_get_config_value_for_site,
    ):
        mock_get_config_value_for_site.return_value = LMS_BASE_URL
        mock_get_learner_portal_url.return_value = "http://test.learner.portal"
        ent_customer, users, course_id, course_details, activation_links = self.setup_notification_test_data()

        email_items = serialize_notification_content(
            ent_customer,
            course_details,
            course_id,
            users,
            admin_enrollment=admin_enrollment,
            activation_links=activation_links,
        )

        def expected_email_item(user, activation_links):
            user_dict = model_to_dict(user, fields=['first_name', 'username', 'user_email', 'email'])
            if 'email' in user_dict:
                user_email = user_dict['email']
            elif 'user_email' in user_dict:
                user_email = user_dict['user_email']
            else:
                raise TypeError(('`user` must have one of either `email` or `user_email`.'))
            course_path = '/courses/{course_id}/course'.format(course_id=course_id)
            course_path = quote("{}?{}".format(course_path, urlencode([])))
            login_or_register = 'register' if is_pending_user(user) else 'login'
            if activation_links is not None and activation_links.get(user_email) is not None:
                enrolled_url = activation_links.get(user_email)
            else:
                enrolled_url = '{site}/{login_or_register}?next={course_path}'.format(
                    site=LMS_BASE_URL,
                    login_or_register=login_or_register,
                    course_path=course_path
                )
            return {
                "user": user_dict,
                "enrolled_in": {
                    'name': course_details.get('title'),
                    'url': enrolled_url,
                    'type': 'course',
                    'start': parse_lms_api_datetime(course_details.get('start'))
                },
                "dashboard_url": exp_dashboard_url,
                "enterprise_customer_uuid": ent_customer.uuid,
                "admin_enrollment": admin_enrollment,
            }

        expected_email_items = [expected_email_item(user, activation_links) for user in users]
        assert email_items == expected_email_items

    def test_get_default_invite_key_expiration_date(self):
        current_time = localized_utcnow()

        expiration_date = get_default_invite_key_expiration_date()
        expected_expiration_date = current_time + timedelta(days=365)
        self.assertEqual(expiration_date.date(), expected_expiration_date.date())

    def test_truncate_string(self):
        """
        Test that `truncate_string` returns the expected string.
        """
        test_string_1 = 'This is a test string'
        self.assertEqual('This is a ', truncate_string(test_string_1, 10))
        self.assertEqual('This is a test string', truncate_string(test_string_1, 100))

        test_string_2 = ''.rjust(MAX_ALLOWED_TEXT_LENGTH + 10, 'x')
        truncated_string = truncate_string(test_string_2)
        self.assertEqual(len(truncated_string), MAX_ALLOWED_TEXT_LENGTH)
