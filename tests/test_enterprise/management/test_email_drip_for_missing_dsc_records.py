"""
Tests for the django management command `email_drip_for_missing_dsc_records`.
"""
import random
from datetime import datetime, timedelta, timezone
from unittest import mock

from pytest import mark
from testfixtures import LogCapture

from django.core.management import call_command
from django.test import TestCase

from consent.models import DataSharingConsent, ProxyDataSharingConsent
from test_utils.factories import (
    EnterpriseCourseEnrollmentFactory,
    EnterpriseCustomerFactory,
    EnterpriseCustomerUserFactory,
    UserFactory,
)

LOGGER_NAME = 'enterprise.management.commands.email_drip_for_missing_dsc_records'


@mark.django_db
class EmailDripForMissingDscRecordsCommandTests(TestCase):
    """
    Test command `email_drip_for_missing_dsc_records`.
    """
    command = 'email_drip_for_missing_dsc_records'

    def create_enrollments(self, num_learners, enrollment_time):
        """
        Create test users and enrollments in database

        """
        course_ids = [
            'course-v1:edX+DemoX+Demo_Course',
            'course-v1:edX+Python+1T2019',
            'course-v1:edX+React+2T2019',
        ]
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        learners = []
        for __ in range(num_learners):
            user = UserFactory.create(is_staff=False, is_active=True)
            learners.append(user)
        learners_data = []
        for learner in learners:
            course_id = random.choice(course_ids)
            learners_data.append(
                {
                    'ENTERPRISE_UUID': enterprise_customer.uuid,
                    'EMAIL': learner.email,
                    'USERNAME': learner.username,
                    'USER_ID': learner.id,
                    'COURSE_ID': course_id
                }
            )
            enterprise_customer_user = EnterpriseCustomerUserFactory(
                user_id=learner.id,
                enterprise_customer=enterprise_customer
            )

            enterprise_course_enrollment = EnterpriseCourseEnrollmentFactory(
                enterprise_customer_user=enterprise_customer_user,
                course_id=course_id,
            )
            enterprise_course_enrollment.created = enrollment_time
            enterprise_course_enrollment.save()

    def setUp(self):
        super().setUp()
        now = datetime.now(timezone.utc)
        # creating enrollments for yesterday.
        self.create_enrollments(num_learners=3, enrollment_time=now - timedelta(days=1))
        # creating enrollments for 10 days before.
        self.create_enrollments(num_learners=5, enrollment_time=now - timedelta(days=10))

    @mock.patch(
        'enterprise.management.commands.email_drip_for_missing_dsc_records.DataSharingConsent.objects.proxied_get'
    )
    @mock.patch('enterprise.management.commands.email_drip_for_missing_dsc_records.utils.track_event')
    @mock.patch('enterprise.management.commands.email_drip_for_missing_dsc_records.Command._get_course_properties')
    @mock.patch('enterprise.management.commands.email_drip_for_missing_dsc_records.is_course_accessed')
    def test_email_drip_for_missing_dsc_records(
            self,
            mock_is_course_accessed,
            mock_get_course_properties,
            mock_event_track,
            mock_dsc_proxied_get
    ):
        """
        Test that email drip event is fired for missing DSC records
        """
        mock_get_course_properties.return_value = 'test_url', 'test_course'
        mock_is_course_accessed.return_value = True
        # test when consent is present
        with LogCapture(LOGGER_NAME) as log:
            mock_dsc_proxied_get.return_value = DataSharingConsent()
            call_command(self.command)
            self.assertEqual(mock_event_track.call_count, 0)
            self.assertIn(
                '[Absent DSC Email] Emails sent for [0] enrollments out of [3] enrollments.',
                log.records[-1].message
            )

        # test when consent is missing, with --no-commit param
        with LogCapture(LOGGER_NAME) as log:
            mock_dsc_proxied_get.return_value = ProxyDataSharingConsent()
            call_command(self.command, '--no-commit')
            self.assertEqual(mock_event_track.call_count, 0)
            self.assertIn(
                '[Absent DSC Email] Emails sent for [3] enrollments out of [3] enrollments.',
                log.records[-1].message
            )

        # test when consent is missing, without passing --no-commit param
        with LogCapture(LOGGER_NAME) as log:
            call_command(self.command)
            self.assertEqual(mock_event_track.call_count, 3)
            self.assertIn(
                '[Absent DSC Email] Emails sent for [3] enrollments out of [3] enrollments.',
                log.records[-1].message
            )

        mock_event_track.reset_mock()

        # test with --enrollment-before param
        enrollment_before_date = (datetime.now(timezone.utc).date() - timedelta(days=5)).isoformat()
        with LogCapture(LOGGER_NAME) as log:
            call_command(self.command, '--enrollment-before', enrollment_before_date)
            self.assertEqual(mock_event_track.call_count, 5)
            self.assertIn(
                '[Absent DSC Email] Emails sent for [5] enrollments out of [5] enrollments.',
                log.records[-1].message
            )
