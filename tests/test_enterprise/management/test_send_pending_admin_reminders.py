"""
Tests for the django management command `send_pending_admin_reminders`.
"""
from io import StringIO
from unittest import mock

from pytest import mark

from django.core.management import call_command
from django.test import TestCase, override_settings

from test_utils import factories

MOCK_PATH = (
    'enterprise.management.commands.send_pending_admin_reminders'
    '.send_enterprise_admin_invite_reminders'
)
MOCK_LOG_PATH = (
    'enterprise.management.commands.send_pending_admin_reminders.log'
)


@mark.django_db
class SendPendingAdminRemindersCommandTests(TestCase):
    """
    Test command `send_pending_admin_reminders`.
    """

    command = 'send_pending_admin_reminders'

    def setUp(self):
        """Set up test fixtures."""
        self.enterprise_customer = factories.EnterpriseCustomerFactory()
        super().setUp()

    @override_settings(
        ENTERPRISE_BRAZE_API_KEY='test-api-key',
        EDX_BRAZE_API_SERVER='https://rest.iad-06.braze.com',
        BRAZE_ADMIN_INVITE_REMINDER_CAMPAIGN_ID='test-campaign-id'
    )
    @mock.patch(MOCK_PATH)
    def test_command_calls_task_function(self, mock_task):
        """
        Test that the command calls the underlying task function.
        """
        mock_task.return_value = {
            'processed': 5, 'sent': 2, 'skipped_active': 1,
            'skipped_not_due': 1, 'skipped_max': 1, 'failures': 0,
        }
        call_command(self.command)
        mock_task.assert_called_once()

    @override_settings(
        ENTERPRISE_BRAZE_API_KEY='test-api-key',
        EDX_BRAZE_API_SERVER='https://rest.iad-06.braze.com',
        BRAZE_ADMIN_INVITE_REMINDER_CAMPAIGN_ID='test-campaign-id'
    )
    @mock.patch(MOCK_PATH)
    def test_command_logs_results(self, mock_task):
        """
        Test that the command logs the results from the task.
        """
        mock_task.return_value = {
            'processed': 10, 'sent': 5, 'skipped_active': 2,
            'skipped_not_due': 2, 'skipped_max': 1, 'failures': 0,
        }
        out = StringIO()
        call_command(self.command, stdout=out)
        output = out.getvalue()
        assert 'Successfully sent 5 reminder(s)' in output
        assert '10 pending invite(s)' in output

    @override_settings(
        ENTERPRISE_BRAZE_API_KEY='test-api-key',
        EDX_BRAZE_API_SERVER='https://rest.iad-06.braze.com',
        BRAZE_ADMIN_INVITE_REMINDER_CAMPAIGN_ID='test-campaign-id'
    )
    @mock.patch(MOCK_PATH)
    def test_command_handles_no_reminders_sent(self, mock_task):
        """
        Test that the command handles the case when no reminders are sent.
        """
        mock_task.return_value = {
            'processed': 5, 'sent': 0, 'skipped_active': 2,
            'skipped_not_due': 3, 'skipped_max': 0, 'failures': 0,
        }
        out = StringIO()
        call_command(self.command, stdout=out)
        assert 'Successfully sent 0 reminder(s)' in out.getvalue()

    @override_settings(
        ENTERPRISE_BRAZE_API_KEY='test-api-key',
        EDX_BRAZE_API_SERVER='https://rest.iad-06.braze.com',
        BRAZE_ADMIN_INVITE_REMINDER_CAMPAIGN_ID='test-campaign-id'
    )
    @mock.patch(MOCK_PATH)
    def test_command_handles_failures(self, mock_task):
        """
        Test that the command handles and reports failures.
        """
        mock_task.return_value = {
            'processed': 10, 'sent': 5, 'skipped_active': 0,
            'skipped_not_due': 2, 'skipped_max': 0, 'failures': 3,
        }
        out = StringIO()
        call_command(self.command, stdout=out)
        assert 'Successfully sent 5 reminder(s)' in out.getvalue()

    @override_settings(
        ENTERPRISE_BRAZE_API_KEY='test-api-key',
        EDX_BRAZE_API_SERVER='https://rest.iad-06.braze.com',
        BRAZE_ADMIN_INVITE_REMINDER_CAMPAIGN_ID='test-campaign-id'
    )
    @mock.patch(MOCK_PATH)
    def test_command_handles_task_exception(self, mock_task):
        """
        Test that the command handles exceptions from the task gracefully.
        """
        mock_task.side_effect = ValueError('Missing Braze configuration')
        err = StringIO()
        with self.assertRaises(ValueError):
            call_command(self.command, stderr=err)
        assert 'Failed to send reminders' in err.getvalue()

    @override_settings(
        ENTERPRISE_BRAZE_API_KEY='test-api-key',
        EDX_BRAZE_API_SERVER='https://rest.iad-06.braze.com',
        BRAZE_ADMIN_INVITE_REMINDER_CAMPAIGN_ID='test-campaign-id'
    )
    @mock.patch(MOCK_PATH)
    def test_command_runs_synchronously(self, mock_task):
        """
        Test that the command calls the task function directly.
        """
        mock_task.return_value = {
            'processed': 0, 'sent': 0, 'skipped_active': 0,
            'skipped_not_due': 0, 'skipped_max': 0, 'failures': 0,
        }
        call_command(self.command)
        mock_task.assert_called_once_with()

    @override_settings(
        ENTERPRISE_BRAZE_API_KEY='test-api-key',
        EDX_BRAZE_API_SERVER='https://rest.iad-06.braze.com',
        BRAZE_ADMIN_INVITE_REMINDER_CAMPAIGN_ID='test-campaign-id'
    )
    @mock.patch(MOCK_LOG_PATH)
    @mock.patch(MOCK_PATH)
    def test_command_logs_execution(self, mock_task, mock_log):
        """
        Test that the command logs the start and completion of execution.
        """
        mock_task.return_value = {
            'processed': 3, 'sent': 1, 'skipped_active': 1,
            'skipped_not_due': 1, 'skipped_max': 0, 'failures': 0,
        }
        call_command(self.command)
        log_messages = [
            call[0][0] for call in mock_log.info.call_args_list
        ]
        assert any('Starting' in msg for msg in log_messages)
        assert any('Completed' in msg for msg in log_messages)
