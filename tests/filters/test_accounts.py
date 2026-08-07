"""
Tests for enterprise.filters.accounts pipeline step.
"""
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from enterprise.filters.accounts import (
    AccountSettingsEnterpriseReadOnlyFieldsStep,
    ActivationEmailEnterpriseContextEnricher,
    ActivationRedirectEnterpriseStep,
)
from enterprise.models import EnterpriseCustomerUser
from test_utils.factories import EnterpriseCustomerUserFactory, UserFactory


class TestAccountSettingsEnterpriseReadOnlyFieldsStep(TestCase):
    """
    Tests for AccountSettingsEnterpriseReadOnlyFieldsStep pipeline step.
    """

    def _make_step(self):
        return AccountSettingsEnterpriseReadOnlyFieldsStep(
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
        mock_objects.filter.return_value.order_by.return_value.select_related.return_value.first.return_value = None
        step = self._make_step()
        fields = set()
        user = self._mock_user()
        result = step.run_filter(readonly_fields=fields, user=user)
        self.assertEqual(result, {"readonly_fields": fields, "user": user})

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
        (
            mock_ecu_objects.filter.return_value
            .order_by.return_value
            .select_related.return_value
            .first.return_value
        ) = mock_ecu
        mock_idp_record = MagicMock()
        mock_idp_record.provider_id = 'saml-ubc'
        mock_idp_objects.filter.return_value = [mock_idp_record]
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
        (
            mock_ecu_objects.filter.return_value
            .order_by.return_value
            .select_related.return_value
            .first.return_value
        ) = MagicMock()
        mock_idp_record = MagicMock()
        mock_idp_record.provider_id = 'saml-ubc'
        mock_idp_objects.filter.return_value = [mock_idp_record]
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

    @patch('enterprise.filters.accounts.EnterpriseCustomerIdentityProvider.objects')
    @patch('enterprise.filters.accounts.EnterpriseCustomerUser.objects')
    def test_returns_unchanged_readonly_fields_when_no_idp_record(
        self, mock_ecu_objects, mock_idp_objects
    ):
        """
        When the enterprise customer has no linked identity provider,
        readonly_fields is returned unchanged.
        """
        user = self._mock_user()
        (
            mock_ecu_objects.filter.return_value
            .order_by.return_value
            .select_related.return_value
            .first.return_value
        ) = MagicMock()
        mock_idp_objects.filter.return_value = []
        step = self._make_step()
        fields = {'existing_field'}
        result = step.run_filter(readonly_fields=fields, user=user)
        self.assertEqual(result["readonly_fields"], fields)

    @patch('enterprise.filters.accounts.EnterpriseCustomerIdentityProvider.objects')
    @patch('enterprise.filters.accounts.EnterpriseCustomerUser.objects')
    def test_returns_unchanged_readonly_fields_when_sync_not_enabled(
        self, mock_ecu_objects, mock_idp_objects
    ):
        """
        When the identity provider exists but sync_learner_profile_data is False,
        readonly_fields is returned unchanged.
        """
        user = self._mock_user()
        (
            mock_ecu_objects.filter.return_value
            .order_by.return_value
            .select_related.return_value
            .first.return_value
        ) = MagicMock()
        mock_idp_record = MagicMock(provider_id='saml-test')
        mock_idp_objects.filter.return_value = [mock_idp_record]
        mock_identity_provider = MagicMock()
        mock_identity_provider.sync_learner_profile_data = False
        mock_tpa = MagicMock()
        mock_tpa.provider.Registry.get.return_value = mock_identity_provider
        step = self._make_step()
        fields = {'existing_field'}
        with patch('enterprise.filters.accounts.third_party_auth', mock_tpa):
            result = step.run_filter(readonly_fields=fields, user=user)
        self.assertEqual(result["readonly_fields"], fields)

    @patch('enterprise.filters.accounts.UserSocialAuth')
    @patch('enterprise.filters.accounts.EnterpriseCustomerIdentityProvider.objects')
    @patch('enterprise.filters.accounts.EnterpriseCustomerUser.objects')
    @override_settings(ENTERPRISE_READONLY_ACCOUNT_FIELDS=['name', 'email', 'country'])
    def test_multiple_identity_providers_only_one_sync_enabled(
        self, mock_ecu_objects, mock_idp_objects, mock_user_social_auth
    ):
        """
        When multiple IdPs exist and only one has sync enabled, readonly fields are still added.
        """
        user = self._mock_user()
        (
            mock_ecu_objects.filter.return_value
            .order_by.return_value
            .select_related.return_value
            .first.return_value
        ) = MagicMock()

        mock_idp_no_sync = MagicMock(provider_id='saml-no-sync')
        mock_idp_with_sync = MagicMock(provider_id='saml-with-sync')
        mock_idp_objects.filter.return_value = [mock_idp_no_sync, mock_idp_with_sync]

        mock_provider_no_sync = MagicMock(sync_learner_profile_data=False, backend_name='tpa-saml-no-sync')
        mock_provider_with_sync = MagicMock(sync_learner_profile_data=True, backend_name='tpa-saml-sync')

        mock_tpa = MagicMock()
        mock_tpa.provider.Registry.get.side_effect = lambda provider_id: (
            mock_provider_no_sync if provider_id == 'saml-no-sync' else mock_provider_with_sync
        )
        mock_user_social_auth.objects.filter.return_value.exists.return_value = True

        with patch('enterprise.filters.accounts.third_party_auth', mock_tpa):
            step = self._make_step()
            result = step.run_filter(readonly_fields=set(), user=user)

        self.assertEqual(result["readonly_fields"], {"name", "email", "country"})

    @patch('enterprise.filters.accounts.EnterpriseCustomerIdentityProvider.objects')
    @patch('enterprise.filters.accounts.EnterpriseCustomerUser.objects')
    def test_returns_unchanged_readonly_fields_when_registry_returns_none(
        self, mock_ecu_objects, mock_idp_objects
    ):
        """
        When Registry.get returns None for an IdP, sync_learner_profile_data stays False
        and readonly_fields is returned unchanged.
        """
        user = self._mock_user()
        (
            mock_ecu_objects.filter.return_value
            .order_by.return_value
            .select_related.return_value
            .first.return_value
        ) = MagicMock()
        mock_idp_record = MagicMock(provider_id='saml-unknown')
        mock_idp_objects.filter.return_value = [mock_idp_record]

        mock_tpa = MagicMock()
        mock_tpa.provider.Registry.get.return_value = None

        fields = {'existing_field'}
        with patch('enterprise.filters.accounts.third_party_auth', mock_tpa):
            step = self._make_step()
            result = step.run_filter(readonly_fields=fields, user=user)

        self.assertEqual(result["readonly_fields"], fields)

    @patch('enterprise.filters.accounts.UserSocialAuth')
    @patch('enterprise.filters.accounts.EnterpriseCustomerIdentityProvider.objects')
    @patch('enterprise.filters.accounts.EnterpriseCustomerUser.objects')
    @override_settings(ENTERPRISE_READONLY_ACCOUNT_FIELDS=['name', 'email'])
    def test_name_excluded_when_sync_enabled_but_no_backend_name(
        self, mock_ecu_objects, mock_idp_objects, mock_user_social_auth
    ):
        """
        When sync is enabled but the provider has no backend_name, provider_backend_names
        stays empty, UserSocialAuth is not queried, has_social_auth stays False,
        and 'name' is excluded (branch #3 behavior).
        """
        user = self._mock_user()
        (
            mock_ecu_objects.filter.return_value
            .order_by.return_value
            .select_related.return_value
            .first.return_value
        ) = MagicMock()
        mock_idp_record = MagicMock(provider_id='saml-ubc')
        mock_idp_objects.filter.return_value = [mock_idp_record]
        # sync is True but backend_name is falsy
        mock_identity_provider = MagicMock(sync_learner_profile_data=True, backend_name=None)
        mock_tpa = MagicMock()
        mock_tpa.provider.Registry.get.return_value = mock_identity_provider

        with patch('enterprise.filters.accounts.third_party_auth', mock_tpa):
            step = self._make_step()
            result = step.run_filter(readonly_fields=set(), user=user)

        self.assertNotIn('name', result["readonly_fields"])
        self.assertIn('email', result["readonly_fields"])
        mock_user_social_auth.objects.filter.assert_not_called()


def _is_enterprise_learner_via_db(user):
    """
    Stand-in for the platform's ``is_enterprise_learner``: a real DB lookup against
    ``EnterpriseCustomerUser`` rather than a canned boolean. The real function lives in
    ``openedx.features.enterprise_support.utils`` (ENT-11576 tracks migrating it into
    edx-enterprise) and isn't importable outside a full LMS install, so it must still be
    patched here — but the patched behavior is driven by real factory-created rows.
    """
    return EnterpriseCustomerUser.objects.filter(user_id=user.id).exists()


_IS_ENTERPRISE_LEARNER_PATH = 'enterprise.filters.accounts.is_enterprise_learner'


class TestActivationEmailEnterpriseContextEnricher(TestCase):
    """
    Tests for ActivationEmailEnterpriseContextEnricher pipeline step.
    """

    def _make_step(self):
        return ActivationEmailEnterpriseContextEnricher(
            "org.openedx.learning.account.activation.email.compose.v1",
            [],
        )

    @patch(_IS_ENTERPRISE_LEARNER_PATH, side_effect=_is_enterprise_learner_via_db)
    def test_flags_enterprise_linked_user(self, _mock_is_enterprise_learner):
        """
        A user linked to an enterprise customer gets is_enterprise_learner=True in the
        message context.
        """
        user = UserFactory()
        EnterpriseCustomerUserFactory(user_id=user.id)
        message_context = {'key': 'abc123'}

        step = self._make_step()
        result = step.run_filter(user=user, message_context=message_context)

        self.assertTrue(result['message_context']['is_enterprise_learner'])
        self.assertIs(result['user'], user)

    @patch(_IS_ENTERPRISE_LEARNER_PATH, side_effect=_is_enterprise_learner_via_db)
    def test_does_not_flag_unlinked_user(self, _mock_is_enterprise_learner):
        """
        A user with no enterprise link gets is_enterprise_learner=False in the message context.
        """
        user = UserFactory()
        message_context = {'key': 'abc123'}

        step = self._make_step()
        result = step.run_filter(user=user, message_context=message_context)

        self.assertFalse(result['message_context']['is_enterprise_learner'])


class TestActivationRedirectEnterpriseStep(TestCase):
    """
    Tests for ActivationRedirectEnterpriseStep pipeline step.
    """

    def _make_step(self):
        return ActivationRedirectEnterpriseStep(
            "org.openedx.learning.account.activation.completed.v1",
            [],
        )

    @patch(_IS_ENTERPRISE_LEARNER_PATH, side_effect=_is_enterprise_learner_via_db)
    def test_preserves_redirect_for_enterprise_learner(self, _mock_is_enterprise_learner):
        """
        An enterprise-linked user with a redirect_url keeps it.
        """
        user = UserFactory()
        EnterpriseCustomerUserFactory(user_id=user.id)

        step = self._make_step()
        result = step.run_filter(user=user, redirect_url='https://example.com/next')

        self.assertEqual(result['redirect_url'], 'https://example.com/next')

    @patch(_IS_ENTERPRISE_LEARNER_PATH, side_effect=_is_enterprise_learner_via_db)
    def test_clears_redirect_for_non_enterprise_learner(self, _mock_is_enterprise_learner):
        """
        A non-enterprise user's redirect_url is cleared so the caller falls back to the
        dashboard.
        """
        user = UserFactory()

        step = self._make_step()
        result = step.run_filter(user=user, redirect_url='https://example.com/next')

        self.assertEqual(result['redirect_url'], '')

    @patch(_IS_ENTERPRISE_LEARNER_PATH, side_effect=_is_enterprise_learner_via_db)
    def test_clears_when_no_redirect_url(self, _mock_is_enterprise_learner):
        """
        Even for an enterprise learner, an empty redirect_url stays empty.
        """
        user = UserFactory()
        EnterpriseCustomerUserFactory(user_id=user.id)

        step = self._make_step()
        result = step.run_filter(user=user, redirect_url='')

        self.assertEqual(result['redirect_url'], '')
