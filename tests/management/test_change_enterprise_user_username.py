"""
Tests for the change_enterprise_user_username management command.
"""
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.test import TestCase


class TestChangeEnterpriseUserUsernameCommand(TestCase):
    """
    Tests for enterprise/management/commands/change_enterprise_user_username.py
    """

    @patch('enterprise.management.commands.change_enterprise_user_username.User.objects')
    @patch('enterprise.management.commands.change_enterprise_user_username.EnterpriseCustomerUser.objects')
    def test_updates_username_for_enterprise_user(self, mock_ecu_objects, mock_user_objects):
        """
        When the user_id belongs to an enterprise user, the username is updated.
        """
        mock_ecu_objects.get.return_value = MagicMock()
        mock_user = MagicMock()
        mock_user_objects.get.return_value = mock_user

        call_command(
            'change_enterprise_user_username',
            user_id='42',
            new_username='corrected_username',
        )

        mock_ecu_objects.get.assert_called_once_with(user_id='42')
        mock_user_objects.get.assert_called_once_with(id='42')
        assert mock_user.username == 'corrected_username'
        mock_user.save.assert_called_once()

    @patch('enterprise.management.commands.change_enterprise_user_username.User.objects')
    @patch('enterprise.management.commands.change_enterprise_user_username.EnterpriseCustomerUser.objects')
    def test_logs_and_exits_when_not_enterprise_user(self, mock_ecu_objects, mock_user_objects):
        """
        When the user_id does not belong to an enterprise user, the command logs and exits.
        """
        from enterprise.models import EnterpriseCustomerUser
        mock_ecu_objects.get.side_effect = EnterpriseCustomerUser.DoesNotExist

        call_command(
            'change_enterprise_user_username',
            user_id='99',
            new_username='any_name',
        )

        # User.objects.get should not be called when user is not enterprise
        mock_user_objects.get.assert_not_called()
