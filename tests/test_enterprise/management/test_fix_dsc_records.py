"""
Tests for the django management command `email_drip_for_missing_dsc_records`.
"""

from pytest import mark
from testfixtures import LogCapture

from django.core.management import call_command
from django.test import TestCase

from consent.models import DataSharingConsent
from enterprise.management.commands.fix_dsc_records import MESSAGE_FORMAT
from test_utils.factories import DataSharingConsentFactory, EnterpriseCustomerFactory

LOGGER_NAME = 'enterprise.management.commands.fix_dsc_records'


@mark.django_db
class FixDSCRecordsCommandTests(TestCase):
    """
    Test command `fix_dsc_records`.
    """
    command = 'fix_dsc_records'

    def setUp(self):
        super().setUp()
        self.enterprise_customer = EnterpriseCustomerFactory()
        self.username = 'edx'
        self.course_101_correct = 'course-v1:edX+E2E-101+course'
        self.course_101_incorrect = 'course-v1:edX E2E-101 course'
        self.course_200_correct = 'course-v1:edX+E2E-200+course'
        self.course_300_incorrect = 'course-v1:edX E2E-300 course'
        self.course_300_correct = 'course-v1:edX+E2E-300+course'
        course_ids = [
            self.course_101_correct, self.course_101_incorrect, self.course_200_correct, self.course_300_incorrect
        ]
        for course_id in course_ids:
            DataSharingConsentFactory(
                enterprise_customer=self.enterprise_customer,
                username=self.username,
                course_id=course_id
            )
        fixed = MESSAGE_FORMAT.format(self.enterprise_customer, self.username, self.course_300_incorrect)
        deleted = MESSAGE_FORMAT.format(self.enterprise_customer, self.username, self.course_101_incorrect)
        self.expect_log_message = "[Fix DSC Records] Execution completed.\nResults: " \
                                  "{'Fixed Record Count': 1, " \
                                  "'Deleted Record Count': 1, " \
                                  "'Fixed Records': ['%s'], " \
                                  "'Deleted Records': ['%s']}" % (fixed, deleted)

    def assert_valid_state(self):
        """
        Validate that data is in valid state.
        """
        dsc_records = DataSharingConsent.objects.all()
        self.assertEqual(dsc_records.count(), 3)
        self.assertTrue(dsc_records.filter(course_id=self.course_101_correct).exists())
        self.assertTrue(dsc_records.filter(course_id=self.course_200_correct).exists())
        self.assertTrue(dsc_records.filter(course_id=self.course_300_correct).exists())
        self.assertFalse(dsc_records.filter(course_id=self.course_101_incorrect).exists())
        self.assertFalse(dsc_records.filter(course_id=self.course_300_incorrect).exists())

    def assert_invalid_state(self):
        """
        Validate that data is in invalid state.
        """
        dsc_records = DataSharingConsent.objects.all()
        self.assertEqual(dsc_records.count(), 4)
        self.assertTrue(dsc_records.filter(course_id=self.course_101_correct).exists())
        self.assertTrue(dsc_records.filter(course_id=self.course_101_incorrect).exists())
        self.assertTrue(dsc_records.filter(course_id=self.course_200_correct).exists())
        self.assertTrue(dsc_records.filter(course_id=self.course_300_incorrect).exists())
        self.assertFalse(dsc_records.filter(course_id=self.course_300_correct).exists())

    def test_fix_dsc_records(self):
        """
        Test fix DSC records.
        """
        with LogCapture(LOGGER_NAME) as log:
            self.assert_invalid_state()
            call_command(self.command)
            self.assert_valid_state()
            self.assertIn(
                self.expect_log_message,
                log.records[-1].message,
            )

    def test_fix_dsc_records_with_no_commit(self):
        """
        Test with --no-commit param.
        """
        with LogCapture(LOGGER_NAME) as log:
            self.assert_invalid_state()
            call_command(self.command, '--no-commit')
            self.assert_invalid_state()
            self.assertIn(
                self.expect_log_message,
                log.records[-1].message,
            )
