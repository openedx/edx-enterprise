"""
Tests for the django management command `nudge_dormant_enrolled_enterprise_learners`.
"""
from unittest import mock

from pytest import mark
from testfixtures import LogCapture

from django.core.management import call_command
from django.test import TestCase

LOGGER_NAME = 'enterprise.management.commands.nudge_dormant_enrolled_enterprise_learners'


@mark.django_db
class NudgeDormantEnrolledEnterpriseLearnersCommandTests(TestCase):
    """
    Test command `nudge_dormant_enrolled_enterprise_learners`.
    """
    command = 'nudge_dormant_enrolled_enterprise_learners'

    @mock.patch('enterprise.management.commands.nudge_dormant_enrolled_enterprise_learners.utils.track_event')
    @mock.patch('enterprise.management.commands.nudge_dormant_enrolled_enterprise_learners.Command.'
                'get_query_results_from_snowflake')
    def test_nudge_dormant_enrolled_enterprise_learners(
            self,
            mock_get_query_results,
            mock_event_track,
    ):
        """
        Test that nudge_dormant_enrolled_enterprise_learners event is sent
        """
        mock_get_query_results.return_value = [list(range(14)) for i in range(10)]
        with LogCapture(LOGGER_NAME) as log:
            call_command(self.command)
            self.assertEqual(mock_event_track.call_count, 10)
            self.assertIn(
                '[Dormant Nudge] Segment event fired for nudge email to dormant enrolled enterprise learners. '
                'LMS User Id: 0, Organization Name: 1, Course Title: 2',
                log.records[-2].message
            )
        mock_event_track.reset_mock()
        # test with --no-commit param
        with LogCapture(LOGGER_NAME) as log:
            call_command(self.command, '--no-commit')
            self.assertEqual(mock_event_track.call_count, 0)
            self.assertIn(
                '[Dormant Nudge] Execution completed.',
                log.records[-1].message
            )

    @mock.patch('enterprise.management.commands.nudge_dormant_enrolled_enterprise_learners.snowflake.connector')
    @mock.patch('enterprise.management.commands.nudge_dormant_enrolled_enterprise_learners.utils.track_event')
    def test_get_query_results_from_snowflake(self, mock_event_track, mock_connector):
        """
        Test get_query_results_from_snowflake works correctly
        """
        mock_connector.connect.return_value.cursor.return_value.fetchall.return_value = [range(14), range(14)]
        with LogCapture(LOGGER_NAME) as log:
            call_command(self.command)
            self.assertEqual(mock_event_track.call_count, 2)
            self.assertIn(
                '[Dormant Nudge] Execution completed.',
                log.records[-1].message
            )
