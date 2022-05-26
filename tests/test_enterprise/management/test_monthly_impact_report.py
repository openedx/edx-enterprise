"""
Tests for the django management command `monthly_impact_report`.
"""
from unittest import mock

from pytest import mark
from testfixtures import LogCapture

from django.core.management import call_command
from django.test import TestCase

LOGGER_NAME = 'enterprise.management.commands.monthly_impact_report'


@mark.django_db
class MonthlyImpactReportCommandTests(TestCase):
    """
    Test command `monthly_impact_report`.
    """
    command = 'monthly_impact_report'

    def setUp(self):
        super().setUp()

    @mock.patch('enterprise.management.commands.monthly_impact_report.utils.track_event')
    @mock.patch('enterprise.management.commands.monthly_impact_report.Command.get_query_results_from_snowflake')
    def test_monthly_impact_report(
            self,
            mock_get_query_results,
            mock_event_track,
    ):
        """
        Test that monthly_impact_report event is sent
        """
        mock_get_query_results.return_value = [list(range(0,50)) for i in range(10)]
        with LogCapture(LOGGER_NAME) as log:
            call_command(self.command)
            self.assertEqual(mock_event_track.call_count, 10)
            self.assertIn(
                '[Monthly Impact Report] Segment event fired for monthly impact report. '
                'lms_user_id: 5, Enterprise Name: 3',
                log.records[-2].message
            )
        mock_event_track.reset_mock()
        # test when consent is missing, with --no-commit param
        with LogCapture(LOGGER_NAME) as log:
            call_command(self.command, '--no-commit')
            self.assertEqual(mock_event_track.call_count, 0)
            self.assertIn(
                '[Monthly Impact Report] Execution completed.',
                log.records[-1].message
            )
