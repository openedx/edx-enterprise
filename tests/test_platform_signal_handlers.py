"""
Tests for enterprise platform signal handlers.
"""
import sys
import unittest
from unittest import mock

from pytest import mark

from django.test.utils import override_settings

from enterprise.models import EnterpriseCustomerUser
from enterprise.platform_signal_handlers import _unlink_enterprise_user_from_idp, handle_social_auth_disconnect
from test_utils.factories import EnterpriseCustomerIdentityProviderFactory, EnterpriseCustomerUserFactory, UserFactory


def _make_platform_mocks(mock_enterprise_customer_for_request, mock_registry):
    """
    Build the sys.modules patch dict needed to satisfy the deferred platform
    imports inside _unlink_enterprise_user_from_idp.
    """
    # openedx.features.enterprise_support.api
    mock_api = mock.MagicMock()
    mock_api.enterprise_customer_for_request = mock_enterprise_customer_for_request
    mock_enterprise_support = mock.MagicMock()
    mock_enterprise_support.api = mock_api
    mock_features = mock.MagicMock()
    mock_features.enterprise_support = mock_enterprise_support
    mock_openedx = mock.MagicMock()
    mock_openedx.features = mock_features

    # common.djangoapps.third_party_auth.provider
    mock_provider = mock.MagicMock()
    mock_provider.Registry = mock_registry
    mock_third_party_auth = mock.MagicMock()
    mock_third_party_auth.provider = mock_provider
    mock_djangoapps = mock.MagicMock()
    mock_djangoapps.third_party_auth = mock_third_party_auth
    mock_common = mock.MagicMock()
    mock_common.djangoapps = mock_djangoapps

    return {
        'openedx': mock_openedx,
        'openedx.features': mock_features,
        'openedx.features.enterprise_support': mock_enterprise_support,
        'openedx.features.enterprise_support.api': mock_api,
        'common': mock_common,
        'common.djangoapps': mock_djangoapps,
        'common.djangoapps.third_party_auth': mock_third_party_auth,
        'common.djangoapps.third_party_auth.provider': mock_provider,
    }


@mark.django_db
class TestUnlinkEnterpriseUserFromIdp(unittest.TestCase):
    """
    Tests for _unlink_enterprise_user_from_idp helper.
    """

    def setUp(self):
        super().setUp()
        self.user = UserFactory()

    def test_unlink_enterprise_user_from_idp(self):
        """
        Verify that the user is unlinked from the enterprise customer when
        the IdP backend matches the enterprise identity provider.
        """
        customer_idp = EnterpriseCustomerIdentityProviderFactory.create(
            provider_id='the-provider',
        )
        customer = customer_idp.enterprise_customer
        EnterpriseCustomerUserFactory.create(
            enterprise_customer=customer,
            user_id=self.user.id,
        )
        mock_customer_for_request = mock.MagicMock(return_value={'uuid': customer.uuid})
        mock_registry = mock.MagicMock()
        mock_registry.get_enabled_by_backend_name.return_value = [
            mock.Mock(provider_id='the-provider'),
        ]
        request = mock.Mock()

        with mock.patch.dict(sys.modules, _make_platform_mocks(mock_customer_for_request, mock_registry)):
            _unlink_enterprise_user_from_idp(request, self.user, idp_backend_name='the-backend-name')

        assert EnterpriseCustomerUser.objects.filter(user_id=self.user.id).count() == 0

    def test_unlink_enterprise_user_from_idp_no_customer_user(self):
        """
        Verify no error when user has no EnterpriseCustomerUser record.
        """
        customer_idp = EnterpriseCustomerIdentityProviderFactory.create(
            provider_id='the-provider',
        )
        customer = customer_idp.enterprise_customer
        mock_customer_for_request = mock.MagicMock(return_value={'uuid': customer.uuid})
        mock_registry = mock.MagicMock()
        mock_registry.get_enabled_by_backend_name.return_value = [
            mock.Mock(provider_id='the-provider'),
        ]
        request = mock.Mock()

        with mock.patch.dict(sys.modules, _make_platform_mocks(mock_customer_for_request, mock_registry)):
            _unlink_enterprise_user_from_idp(request, self.user, idp_backend_name='the-backend-name')

        assert EnterpriseCustomerUser.objects.filter(user_id=self.user.id).count() == 0


@mark.django_db
class TestHandleSocialAuthDisconnect(unittest.TestCase):
    """
    Tests for handle_social_auth_disconnect signal handler.
    """

    @override_settings(FEATURES={'ENABLE_ENTERPRISE_INTEGRATION': True})
    @mock.patch(
        'enterprise.platform_signal_handlers._unlink_enterprise_user_from_idp',
    )
    def test_calls_unlink_when_request_present(self, mock_unlink):
        """
        Test that _unlink_enterprise_user_from_idp is called when request is present.
        """
        request = mock.MagicMock()
        user = mock.MagicMock()
        saml_backend = mock.MagicMock()

        handle_social_auth_disconnect(
            sender=None,
            request=request,
            user=user,
            saml_backend=saml_backend,
        )
        mock_unlink.assert_called_once_with(request, user, saml_backend.name)

    @override_settings(FEATURES={'ENABLE_ENTERPRISE_INTEGRATION': True})
    @mock.patch(
        'enterprise.platform_signal_handlers._unlink_enterprise_user_from_idp',
    )
    def test_skips_unlink_when_request_is_none(self, mock_unlink):
        """
        Test that _unlink_enterprise_user_from_idp is not called when request is None.
        """
        user = mock.MagicMock()
        saml_backend = mock.MagicMock()

        handle_social_auth_disconnect(
            sender=None,
            request=None,
            user=user,
            saml_backend=saml_backend,
        )
        mock_unlink.assert_not_called()

    @override_settings(FEATURES={'ENABLE_ENTERPRISE_INTEGRATION': False})
    @mock.patch(
        'enterprise.platform_signal_handlers._unlink_enterprise_user_from_idp',
    )
    def test_skips_unlink_when_enterprise_integration_disabled(self, mock_unlink):
        """
        Test that _unlink_enterprise_user_from_idp is not called when
        ENABLE_ENTERPRISE_INTEGRATION is False.
        """
        request = mock.MagicMock()
        user = mock.MagicMock()
        saml_backend = mock.MagicMock()

        handle_social_auth_disconnect(
            sender=None,
            request=request,
            user=user,
            saml_backend=saml_backend,
        )
        mock_unlink.assert_not_called()
