"""
Tests for enterprise.filters.accounts pipeline step.
"""
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from enterprise.filters.accounts import AccountSettingsReadOnlyFieldsStep


class TestAccountSettingsReadOnlyFieldsStep(TestCase):
    """
    Tests for AccountSettingsReadOnlyFieldsStep pipeline step.
    """

    def _make_step(self):
        return AccountSettingsReadOnlyFieldsStep(
            "org.openedx.learning.account.settings.read_only_fields.requested.v1",
            [],
        )

    def _mock_user(self, user_id=42):
        user = MagicMock()
        user.id = user_id
        return user

    @patch('enterprise.filters.accounts.EnterpriseCustomerUser.objects')
    def test_returns_unchanged_readonly_fields_when_no_enterprise_user(self, mock_objects):
        """
        When the user has no enterprise link, readonly_fields is returned unchanged.
        """
        from enterprise.models import EnterpriseCustomerUser
        mock_objects.select_related.return_value.get.side_effect = EnterpriseCustomerUser.DoesNotExist
        step = self._make_step()
        fields = set()
        result = step.run_filter(readonly_fields=fields, user=self._mock_user())
        self.assertEqual(result, {"readonly_fields": fields})

    @patch('enterprise.filters.accounts.UserSocialAuth')
    @patch('enterprise.filters.accounts.EnterpriseCustomerIdentityProvider.objects')
    @patch('enterprise.filters.accounts.EnterpriseCustomerUser.objects')
    @override_settings(ENTERPRISE_READONLY_ACCOUNT_FIELDS=['name', 'email', 'country'])
    def test_adds_readonly_fields_when_sso_sync_enabled(
        self, mock_ecu_objects, mock_idp_objects, mock_user_social_auth
    ):
        """
        When enterprise SSO sync is enabled and social auth record exists,
        ENTERPRISE_READONLY_ACCOUNT_FIELDS are added to readonly_fields.
        """
        user = self._mock_user()
        mock_ecu = MagicMock()
        mock_ecu_objects.select_related.return_value.get.return_value = mock_ecu
        mock_idp_record = MagicMock()
        mock_idp_record.provider_id = 'saml-ubc'
        mock_idp_objects.get.return_value = mock_idp_record
        mock_identity_provider = MagicMock()
        mock_identity_provider.sync_learner_profile_data = True
        mock_identity_provider.backend_name = 'tpa-saml'
        mock_user_social_auth.objects.filter.return_value.exists.return_value = True

        mock_tpa = MagicMock()
        mock_tpa.provider.Registry.get.return_value = mock_identity_provider
        with patch('enterprise.filters.accounts.third_party_auth', mock_tpa):
            step = self._make_step()
            result = step.run_filter(
                readonly_fields=set(),
                user=user,
            )

        self.assertEqual(result["readonly_fields"], {"name", "email", "country"})

    @patch('enterprise.filters.accounts.UserSocialAuth')
    @patch('enterprise.filters.accounts.EnterpriseCustomerIdentityProvider.objects')
    @patch('enterprise.filters.accounts.EnterpriseCustomerUser.objects')
    @override_settings(ENTERPRISE_READONLY_ACCOUNT_FIELDS=['name', 'email'])
    def test_name_not_added_without_social_auth_record(
        self, mock_ecu_objects, mock_idp_objects, mock_user_social_auth
    ):
        """
        The 'name' field is not added when the user has no UserSocialAuth record.
        """
        user = self._mock_user()
        mock_ecu_objects.select_related.return_value.get.return_value = MagicMock()
        mock_idp_record = MagicMock()
        mock_idp_record.provider_id = 'saml-ubc'
        mock_idp_objects.get.return_value = mock_idp_record
        mock_identity_provider = MagicMock()
        mock_identity_provider.sync_learner_profile_data = True
        mock_identity_provider.backend_name = 'tpa-saml'
        mock_user_social_auth.objects.filter.return_value.exists.return_value = False

        mock_tpa = MagicMock()
        mock_tpa.provider.Registry.get.return_value = mock_identity_provider
        with patch('enterprise.filters.accounts.third_party_auth', mock_tpa):
            step = self._make_step()
            result = step.run_filter(
                readonly_fields=set(),
                user=user,
            )

        self.assertNotIn("name", result["readonly_fields"])
        self.assertIn("email", result["readonly_fields"])
