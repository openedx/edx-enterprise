"""
Tests for the djagno management command `create_enterprise_course_enrollments`.
"""
from __future__ import absolute_import, unicode_literals

import ddt
import mock
from faker import Factory as FakerFactory
from pytest import mark

from django.core.management import CommandError, call_command
from django.test import TestCase

from enterprise.management.commands.create_enterprise_course_enrollments import HttpClientError
from test_utils.factories import (
    EnterpriseCourseEnrollmentFactory,
    EnterpriseCustomerFactory,
    EnterpriseCustomerUserFactory,
    UserFactory,
)


@mark.django_db
@ddt.ddt
class CreateEnterpriseCourseEnrollmentCommandTests(TestCase):
    """
    Test command `create_enterprise_course_enrollments`.
    """
    command = 'create_enterprise_course_enrollments'

    def setUp(self):
        self.user = UserFactory.create(is_staff=True, is_active=True)
        self.enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        self.enterprise_customer_user = EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=self.enterprise_customer
        )
        super(CreateEnterpriseCourseEnrollmentCommandTests, self).setUp()

    def test_command_without_required_parameters(self):
        """
        Test that calling command without the required parameters, enterprise
        UUID and course run ids raise exception.
        """
        expected_command_log_message = 'Please provide the enterprise UUID and comma-delimited list of course run IDs.'
        with self.assertRaisesMessage(CommandError, expected_command_log_message):
            call_command(self.command, commit=False)

    def test_command_for_invalid_enterprise_cutomer(self):
        """
        Test that calling command with invalid enterprise UUID raise exception.
        """
        faker = FakerFactory.create()
        invalid_enterprise_uuid = faker.uuid4()  # pylint: disable=no-member
        courses = 'course-v1:edX+DemoX+Demo_Course'
        expected_command_log_message = 'No enterprise customer found for UUID: {uuid}'.format(
            uuid=invalid_enterprise_uuid
        )
        with self.assertRaisesMessage(CommandError, expected_command_log_message):
            call_command(self.command, enterprise_uuid=invalid_enterprise_uuid, courses=courses, commit=False)

    @mock.patch('enterprise.management.commands.create_enterprise_course_enrollments.CourseApiClient')
    @mock.patch('enterprise.management.commands.create_enterprise_course_enrollments.LOGGER')
    def test_command_for_non_existing_course(self, logger_mock, course_api_client_mock):
        """
        Test that the command skips enrollments for the course which doesn't
        exist.
        """
        non_existing_course_id = 'course-v1:Non+Existing+Course'
        course_api_client = course_api_client_mock.return_value
        course_api_client.get_course_details.side_effect = HttpClientError
        call_command(
            self.command,
            enterprise_uuid=self.enterprise_customer.uuid,
            courses=non_existing_course_id,
            commit=False,
        )

        expected_course_api_log_message = 'Failed to retrieve course details from LMS API for {course}'.format(
            course=non_existing_course_id
        )
        expected_command_log_message = 'Course {course} not found, skipping.'.format(course=non_existing_course_id)
        logger_mock.error.assert_called_with(expected_course_api_log_message)
        logger_mock.warning.assert_called_with(expected_command_log_message)

    @mock.patch('enterprise.management.commands.create_enterprise_course_enrollments.CourseApiClient')
    @mock.patch('enterprise.management.commands.create_enterprise_course_enrollments.EnrollmentApiClient')
    @mock.patch('enterprise.management.commands.create_enterprise_course_enrollments.LOGGER')
    def test_command_for_missing_enterprise_course_enrollment(
            self, logger_mock,
            enrollment_api_client_mock,
            course_api_client_mock
    ):
        """
        Test that the command adds missing enterprise course enrollment records
        against the provided enterprise courses for the enterprise learners
        which are enrolled but don't have enterprise course enrollment record.
        """
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        course_api_client = course_api_client_mock.return_value
        course_api_client.get_course_details.return_value = {
            'name': 'edX Demo Course',
        }
        enrollment_api_client = enrollment_api_client_mock.return_value
        enrollment_api_client.get_course_enrollment.return_value = {
            'user': 'john_doe',
            'is_active': True,
        }
        call_command(
            self.command,
            enterprise_uuid=self.enterprise_customer.uuid,
            courses=course_id,
            commit=False,
        )

        expected_enrolled_users_count = 1
        expected_ent_cour_enroll_count = 1
        expected_command_log_message = 'Created {created} missing EnterpriseCourseEnrollments ' \
                                       'for {enrolled} enterprise learners enrolled in {course}.'.format(
                                           created=expected_ent_cour_enroll_count,
                                           enrolled=expected_enrolled_users_count,
                                           course=course_id,
                                       )
        logger_mock.info.assert_called_with(expected_command_log_message)

    @mock.patch('enterprise.management.commands.create_enterprise_course_enrollments.CourseApiClient')
    @mock.patch('enterprise.management.commands.create_enterprise_course_enrollments.EnrollmentApiClient')
    @mock.patch('enterprise.management.commands.create_enterprise_course_enrollments.LOGGER')
    def test_command_for_un_enrolled_learners(
            self, logger_mock,
            enrollment_api_client_mock,
            course_api_client_mock
    ):
        """
        Test that the command don't add enterprise course enrollment records
        for the enterprise learners which are not enrolled in the provided
        enterprise courses.
        """
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        course_api_client = course_api_client_mock.return_value
        course_api_client.get_course_details.return_value = {
            'name': 'edX Demo Course',
        }
        enrollment_api_client = enrollment_api_client_mock.return_value
        enrollment_api_client.get_course_enrollment.return_value = None
        call_command(
            self.command,
            enterprise_uuid=self.enterprise_customer.uuid,
            courses=course_id,
            commit=False,
        )

        expected_enrolled_users_count = 0
        expected_ent_cour_enroll_count = 0
        expected_command_log_message = 'Created {created} missing EnterpriseCourseEnrollments ' \
                                       'for {enrolled} enterprise learners enrolled in {course}.'.format(
                                           created=expected_ent_cour_enroll_count,
                                           enrolled=expected_enrolled_users_count,
                                           course=course_id,
                                       )
        logger_mock.info.assert_called_with(expected_command_log_message)

    @mock.patch('enterprise.management.commands.create_enterprise_course_enrollments.CourseApiClient')
    @mock.patch('enterprise.management.commands.create_enterprise_course_enrollments.EnrollmentApiClient')
    @mock.patch('enterprise.management.commands.create_enterprise_course_enrollments.LOGGER')
    def test_command_for_learners_with_existing_enterprise_course_enrollment(
            self, logger_mock,
            enrollment_api_client_mock,
            course_api_client_mock
    ):
        """
        Test that the command don't add enterprise course enrollment records
        for the enterprise learners which have existing enterprise course
        enrollment against the provided enterprise courses.
        """
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        course_api_client = course_api_client_mock.return_value
        course_api_client.get_course_details.return_value = {
            'name': 'edX Demo Course',
        }
        enrollment_api_client = enrollment_api_client_mock.return_value
        enrollment_api_client.get_course_enrollment.return_value = {
            'user': 'john_doe',
            'is_active': True,
        }
        EnterpriseCourseEnrollmentFactory(
            course_id=course_id,
            enterprise_customer_user=self.enterprise_customer_user,
        )
        call_command(
            self.command,
            enterprise_uuid=self.enterprise_customer.uuid,
            courses=course_id,
            commit=False,
        )

        expected_enrolled_users_count = 1
        expected_ent_cour_enroll_count = 0
        expected_command_log_message = 'Created {created} missing EnterpriseCourseEnrollments ' \
                                       'for {enrolled} enterprise learners enrolled in {course}.'.format(
                                           created=expected_ent_cour_enroll_count,
                                           enrolled=expected_enrolled_users_count,
                                           course=course_id,
                                       )
        logger_mock.info.assert_called_with(expected_command_log_message)
