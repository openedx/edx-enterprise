"""
Tests for the send_enterprise_admin_invite_reminders management command.
"""
import unittest
from io import StringIO
from unittest import mock

from pytest import mark

from django.core.management import call_command


@mark.django_db
class TestSendEnterpriseAdminInviteRemindersCommand(unittest.TestCase):
    """
    Tests for the send_enterprise_admin_invite_reminders management command.
    """

    @mock.patch(
        'enterprise.management.commands.send_enterprise_admin_invite_reminders'
        '.send_enterprise_admin_invite_reminders'
    )
    def test_handle_sync(self, mock_task):
        """
        Assert the command runs the task synchronously by default.
        """
        out = StringIO()
        call_command('send_enterprise_admin_invite_reminders', stdout=out)
        mock_task.assert_called_once()
        mock_task.delay.assert_not_called()
        assert 'Finished' in out.getvalue()

    @mock.patch(
        'enterprise.management.commands.send_enterprise_admin_invite_reminders'
        '.send_enterprise_admin_invite_reminders'
    )
    def test_handle_async(self, mock_task):
        """
        Assert the command dispatches the task asynchronously with --async flag.
        """
        out = StringIO()
        call_command('send_enterprise_admin_invite_reminders', '--async', stdout=out)
        mock_task.delay.assert_called_once()
        assert 'asynchronously' in out.getvalue()
