"""
Tests for consent signal handlers.
"""
import unittest

from pytest import mark

from consent.models import DataSharingConsent
from consent.signals import retire_users_data_sharing_consent
from test_utils.factories import DataSharingConsentFactory, EnterpriseCustomerFactory, UserFactory


@mark.django_db
class TestRetireUsersDataSharingConsent(unittest.TestCase):
    """
    Tests for the retire_users_data_sharing_consent signal handler.
    """

    def setUp(self):
        super().setUp()
        self.user = UserFactory()
        self.retired_username = f'retired__{self.user.username}'
        self.enterprise_customer = EnterpriseCustomerFactory()
        self.consent = DataSharingConsentFactory(
            username=self.user.username,
            enterprise_customer=self.enterprise_customer,
        )

    def _send_signal(self):
        """Helper to invoke the handler as the signal would."""
        retire_users_data_sharing_consent(
            sender=None,
            user=self.user,
            retired_username=self.retired_username,
            retired_email=f'retired__{self.user.email}',
        )

    def test_retires_username_on_consent_records(self):
        self._send_signal()

        self.consent.refresh_from_db()
        assert self.consent.username == self.retired_username

    def test_no_consent_records_with_original_username_remain(self):
        original_username = self.user.username
        self._send_signal()

        assert not DataSharingConsent.objects.filter(username=original_username).exists()

    def test_idempotent_when_already_retired(self):
        """Calling the handler twice does not raise and leaves data in the correct state."""
        self._send_signal()
        self._send_signal()

        self.consent.refresh_from_db()
        assert self.consent.username == self.retired_username
