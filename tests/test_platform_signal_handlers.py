"""
Tests for enterprise.platform_signal_handlers.
"""
from unittest.mock import MagicMock, patch

from django.test import TestCase

from enterprise.platform_signal_handlers import handle_user_retirement


class TestHandleUserRetirement(TestCase):
    """
    Tests for handle_user_retirement signal handler.
    """

    def _make_user(self, user_id=42, username="learner", email="learner@example.com"):
        """Create and return a mock user object with the given attributes."""
        user = MagicMock()
        user.id = user_id
        user.username = username
        user.email = email
        return user

    @patch('enterprise.platform_signal_handlers.PendingEnterpriseCustomerUser.objects')
    @patch('enterprise.platform_signal_handlers.DataSharingConsent.objects')
    def test_retires_dsc_records(self, mock_dsc_objects, mock_pending_objects):
        """
        DataSharingConsent records are updated to use the retired_username.
        """
        mock_dsc_objects.filter.return_value.update.return_value = 2
        mock_pending_objects.filter.return_value.update.return_value = 0

        user = self._make_user()
        handle_user_retirement(
            sender=None,
            user=user,
            retired_username="retired__abc123",
            retired_email="retired__abc123@retired.invalid",
        )

        mock_dsc_objects.filter.assert_called_once_with(username="learner")
        mock_dsc_objects.filter.return_value.update.assert_called_once_with(
            username="retired__abc123"
        )

    @patch('enterprise.platform_signal_handlers.PendingEnterpriseCustomerUser.objects')
    @patch('enterprise.platform_signal_handlers.DataSharingConsent.objects')
    def test_retires_pending_enterprise_customer_user_records(self, mock_dsc_objects, mock_pending_objects):
        """
        PendingEnterpriseCustomerUser records are updated to use the retired_email.
        """
        mock_dsc_objects.filter.return_value.update.return_value = 0
        mock_pending_objects.filter.return_value.update.return_value = 1

        user = self._make_user()
        handle_user_retirement(
            sender=None,
            user=user,
            retired_username="retired__abc123",
            retired_email="retired__abc123@retired.invalid",
        )

        mock_pending_objects.filter.assert_called_once_with(user_email="learner@example.com")
        mock_pending_objects.filter.return_value.update.assert_called_once_with(
            user_email="retired__abc123@retired.invalid"
        )

    @patch('enterprise.platform_signal_handlers.PendingEnterpriseCustomerUser.objects')
    @patch('enterprise.platform_signal_handlers.DataSharingConsent.objects')
    def test_accepts_extra_kwargs_without_error(self, mock_dsc_objects, mock_pending_objects):
        """
        The handler ignores unknown kwargs (forward-compatible with signal additions).
        """
        mock_dsc_objects.filter.return_value.update.return_value = 0
        mock_pending_objects.filter.return_value.update.return_value = 0

        user = self._make_user()
        # Should not raise even with unexpected kwargs
        handle_user_retirement(
            sender=None,
            user=user,
            retired_username="retired__xyz",
            retired_email="retired__xyz@retired.invalid",
            unknown_future_kwarg="ignored",
        )
