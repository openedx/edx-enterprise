"""
Tests for the `edx-enterprise` tpa-pipeline module.
"""

import unittest
from unittest import mock

import ddt
from pytest import mark

from django.contrib.messages.storage import fallback
from django.contrib.sessions.backends import cache
from django.test import RequestFactory
from django.test.utils import override_settings

from enterprise.models import EnterpriseCustomerUser
from enterprise.tpa_pipeline import (
    enterprise_associate_by_email,
    get_enterprise_customer_for_running_pipeline,
    handle_enterprise_logistration,
)
from test_utils.factories import (
    EnterpriseCustomerFactory,
    EnterpriseCustomerIdentityProviderFactory,
    EnterpriseCustomerSsoConfigurationFactory,
    UserFactory,
)


@ddt.ddt
@mark.django_db
class TestTpaPipeline(unittest.TestCase):
    """
    Test functions in the tpa_pipeline module.
    """

    def setUp(self):
        ecidp = EnterpriseCustomerIdentityProviderFactory(provider_id='provider_slug')
        self.customer = ecidp.enterprise_customer
        self.user = UserFactory(is_active=True)
        self.request_factory = RequestFactory()
        self.request = self.request_factory.get('/')
        self.request.session = cache.SessionStore()
        super().setUp()

    def get_mocked_sso_backend(self):
        """
        Get a mocked request backend with mocked strategy.
        """
        # Monkey-patch storage for messaging;   pylint: disable=protected-access
        self.request._messages = fallback.FallbackStorage(self.request)

        strategy_mock = mock.MagicMock(request=self.request)
        backend = mock.MagicMock(
            name=None,
            strategy=strategy_mock,
        )
        return backend

    @ddt.data(False, True)
    def test_handle_enterprise_logistration_user_linking(
            self,
            user_is_active,
    ):
        """
        Test that we create an EnterpriseCustomerUser, then return.
        """
        backend = self.get_mocked_sso_backend()
        self.user = UserFactory(is_active=user_is_active)
        with mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_running_pipeline') as fake_get_ec:
            with mock.patch('enterprise.tpa_pipeline.get_sso_provider') as fake_get_sso_provider:
                with mock.patch('enterprise.tpa_pipeline.validate_provider_config'):
                    enterprise_customer = EnterpriseCustomerFactory(
                        enable_data_sharing_consent=False
                    )
                    provider_config = EnterpriseCustomerIdentityProviderFactory(enterprise_customer=enterprise_customer)
                    fake_get_sso_provider.return_value = provider_config.provider_id

                    fake_get_ec.return_value = enterprise_customer
                    assert handle_enterprise_logistration.__wrapped__(backend, self.user) is None
                    assert EnterpriseCustomerUser.objects.filter(
                        enterprise_customer=enterprise_customer,
                        user_id=self.user.id,
                        active=True
                    ).count() == 1

    def test_handle_enterprise_logistration_not_user_linking(self):
        """
        Test if there is not any enterprise customer then EnterpriseCustomerUser would not be associated with it.
        """
        backend = self.get_mocked_sso_backend()
        self.user = UserFactory()
        with mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_running_pipeline') as fake_get_ec:
            with mock.patch('enterprise.tpa_pipeline.get_sso_provider') as fake_get_sso_provider:
                enterprise_customer = EnterpriseCustomerFactory(
                    enable_data_sharing_consent=False
                )
                fake_get_ec.return_value = None
                fake_get_sso_provider.return_value = None
                assert handle_enterprise_logistration.__wrapped__(backend, self.user) is None
                assert EnterpriseCustomerUser.objects.filter(
                    enterprise_customer=enterprise_customer,
                    user_id=self.user.id,
                    active=True
                ).count() == 0

    def test_handle_enterprise_logistration_user_multiple_enterprises_linking(self):
        """
        Test that if user has multiple enterprise_customers then active status of latest
         enterprise_customer with which user is logged in will be marked as True and active
          status of other enterprise_customers will be marked as False.
        """
        backend = self.get_mocked_sso_backend()
        self.user = UserFactory(is_active=True)
        with mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_running_pipeline') as fake_get_ec:
            with mock.patch('enterprise.tpa_pipeline.get_sso_provider') as fake_get_sso_provider:
                with mock.patch('enterprise.tpa_pipeline.validate_provider_config'):
                    enterprise_customer = EnterpriseCustomerFactory(
                        enable_data_sharing_consent=False
                    )
                    enterprise_customer_old = EnterpriseCustomerFactory(
                        enable_data_sharing_consent=False
                    )
                    EnterpriseCustomerUser.objects.create(
                        enterprise_customer=enterprise_customer_old,
                        user_id=self.user.id,
                        active=True
                    )
                    fake_get_ec.return_value = enterprise_customer
                    fake_get_sso_provider.return_value = 'test-sso-provider-id'
                    assert handle_enterprise_logistration.__wrapped__(backend, self.user) is None
                    assert EnterpriseCustomerUser.objects.filter(
                        enterprise_customer=enterprise_customer,
                        user_id=self.user.id,
                        active=True
                    ).count() == 1
                    assert EnterpriseCustomerUser.objects.filter(
                        enterprise_customer=enterprise_customer_old,
                        user_id=self.user.id,
                        active=False
                    ).count() == 1

    @ddt.data(
        (False, 'facebook'),
        (True, 'facebook'),
        (True, 'google-oauth2'),
        (False, 'google-oauth2'),
    )
    @ddt.unpack
    def test_social_auth_user_login_associated_with_multiple_enterprise(self,
                                                                        new_association,
                                                                        backend_name):
        """
        Test redirect to enterprise selection page, if socialAuth user has LMS attached account
        and part of multiple enterprises
        """
        kwargs = {'new_association': new_association}
        backend = self.get_mocked_sso_backend()
        backend.name = backend_name
        backend.strategy.session_get.return_value = 'not-an-enrollment-url'
        self.user = UserFactory(is_active=True)
        enterprise_customer = EnterpriseCustomerFactory(
            enable_data_sharing_consent=False
        )
        enterprise_customer_old = EnterpriseCustomerFactory(
            enable_data_sharing_consent=False
        )
        EnterpriseCustomerUser.objects.create(
            enterprise_customer=enterprise_customer_old,
            user_id=self.user.id,
            active=False
        )
        EnterpriseCustomerUser.objects.create(
            enterprise_customer=enterprise_customer,
            user_id=self.user.id,
            active=True
        )
        with mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_running_pipeline') as fake_get_ec:
            with mock.patch('enterprise.tpa_pipeline.select_enterprise_page_as_redirect_url') as ent_page_redirect:
                with mock.patch('enterprise.tpa_pipeline.get_sso_provider') as fake_get_sso_provider:
                    fake_get_sso_provider.return_value = None
                    fake_get_ec.return_value = None
                    handle_enterprise_logistration.__wrapped__(backend, self.user, **kwargs)
                    if new_association:
                        ent_page_redirect.assert_not_called()
                    else:
                        ent_page_redirect.assert_called_once()

    @ddt.data(
        (False, 'facebook'),
        (False, 'google-oauth2'),
    )
    @ddt.unpack
    def test_social_auth_user_login_associated_with_one_enterprise(self, new_association, backend_name):
        """
        Test that if socialAuth user has edx attached account and is part of one enterprises then redirection url
        is not changed
        """
        kwargs = {'new_association': new_association}
        backend = self.get_mocked_sso_backend()
        backend.name = backend_name
        backend.strategy.session_get.return_value = 'not-an-enrollment-url'
        self.user = UserFactory(is_active=True)
        enterprise_customer = EnterpriseCustomerFactory(
            enable_data_sharing_consent=False
        )

        EnterpriseCustomerUser.objects.create(
            enterprise_customer=enterprise_customer,
            user_id=self.user.id,
            active=False
        )
        with mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_running_pipeline') as fake_get_ec:
            with mock.patch('enterprise.tpa_pipeline.select_enterprise_page_as_redirect_url') as ent_page_redirect:
                with mock.patch('enterprise.tpa_pipeline.get_sso_provider') as fake_get_sso_provider:
                    fake_get_sso_provider.return_value = None
                    fake_get_ec.return_value = None
                    handle_enterprise_logistration.__wrapped__(backend, self.user, **kwargs)
                    ent_page_redirect.assert_not_called()

    @ddt.data(
        (True, False, 'facebook'),
        (False, False, 'facebook'),
        (True, True, 'facebook'),
        (False, True, 'facebook'),
        (True, True, 'google-oauth2'),
        (False, True, 'google-oauth2'),
        (True, False, 'google-oauth2'),
        (False, False, 'google-oauth2'),
    )
    @ddt.unpack
    def test_bypass_enterprise_selection_page_for_enrollment_url_login(self,
                                                                       using_enrollment_url,
                                                                       new_association,
                                                                       backend_name):
        """
        Test that enterprise selection page is bypassed if socialAuth user is part of multiple enterprises
        and uses an enrollment url for login
        """
        kwargs = {'new_association': new_association}
        backend = self.get_mocked_sso_backend()
        backend.name = backend_name
        if using_enrollment_url:
            backend.strategy.session_get.return_value = '/enterprise/12e87171-fb0a/course/course-v1:Test/enroll'
        else:
            backend.strategy.session_get.return_value = 'not-an-enrollment-url'
        self.user = UserFactory(is_active=True)
        enterprise_customer = EnterpriseCustomerFactory(
            enable_data_sharing_consent=False
        )
        enterprise_customer_old = EnterpriseCustomerFactory(
            enable_data_sharing_consent=False
        )
        EnterpriseCustomerUser.objects.create(
            enterprise_customer=enterprise_customer_old,
            user_id=self.user.id,
            active=False
        )
        EnterpriseCustomerUser.objects.create(
            enterprise_customer=enterprise_customer,
            user_id=self.user.id,
            active=True
        )
        with mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_running_pipeline') as fake_get_ec:
            with mock.patch(
                    'enterprise.tpa_pipeline.select_enterprise_page_as_redirect_url') as ent_page_redirect:
                with mock.patch('enterprise.tpa_pipeline.get_sso_provider') as fake_get_sso_provider:
                    fake_get_sso_provider.return_value = None
                    fake_get_ec.return_value = None
                    handle_enterprise_logistration.__wrapped__(backend, self.user, **kwargs)
                    if new_association or using_enrollment_url:
                        ent_page_redirect.assert_not_called()
                    else:
                        ent_page_redirect.assert_called_once()

    def test_get_ec_for_pipeline(self):
        """
        Test that we get the correct results for a given running pipeline.
        """
        with mock.patch('enterprise.tpa_pipeline.Registry') as fake_registry:
            provider = mock.MagicMock(provider_id='provider_slug')
            fake_registry.get_from_pipeline.return_value = provider
            assert get_enterprise_customer_for_running_pipeline(self.request, 'pipeline') == self.customer

            # pipeline is None
            assert get_enterprise_customer_for_running_pipeline(self.request, None) is None

            # provider_id is None
            provider = mock.MagicMock(provider_id=None)
            fake_registry.get_from_pipeline.return_value = provider
            assert get_enterprise_customer_for_running_pipeline(self.request, 'pipeline') is None

    def test_enterprise_logistration_validates_sso_orchestration_config(self):
        """
        Test that an enterprise logistration flow validates the customer's sso integration config.
        """
        backend = self.get_mocked_sso_backend()
        self.user = UserFactory(is_active=True)
        with mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_running_pipeline') as fake_get_ec:
            with mock.patch('enterprise.tpa_pipeline.get_sso_provider') as fake_get_sso_provider:
                enterprise_customer = EnterpriseCustomerFactory(
                    enable_data_sharing_consent=False
                )
                customer_sso_integration_config = EnterpriseCustomerSsoConfigurationFactory(
                    enterprise_customer=enterprise_customer,
                    validated_at=None,
                )
                customer_sso_integration_config.save()
                EnterpriseCustomerUser.objects.create(
                    enterprise_customer=enterprise_customer,
                    user_id=self.user.id,
                    active=True,
                )
                fake_get_ec.return_value = enterprise_customer
                fake_get_sso_provider.return_value = 'test-sso-provider-id'

                assert handle_enterprise_logistration.__wrapped__(backend, self.user) is None
                customer_sso_integration_config.refresh_from_db()
                assert customer_sso_integration_config.validated_at is not None


@mark.django_db
class TestEnterpriseAssociateByEmail(unittest.TestCase):
    """
    Tests for the enterprise_associate_by_email pipeline step.
    """

    def setUp(self):
        super().setUp()
        self.idp = EnterpriseCustomerIdentityProviderFactory(provider_id='test-provider-id')
        self.enterprise_customer = self.idp.enterprise_customer
        self.user = UserFactory(is_active=True, email='existing@example.com')
        self.request_factory = RequestFactory()
        # is_saml_provider is imported from openedx-platform and is None in the test env.
        self.is_saml_provider_patcher = mock.patch('enterprise.tpa_pipeline.is_saml_provider')
        self.mock_is_saml_provider = self.is_saml_provider_patcher.start()
        self.saml_provider_mock = mock.MagicMock(provider_id='test-provider-id')
        self.mock_is_saml_provider.return_value = (True, self.saml_provider_mock)

    def tearDown(self):
        self.is_saml_provider_patcher.stop()
        super().tearDown()

    def _make_strategy(self, provider_id='test-provider-id'):
        """Return a mock strategy whose request.backend has the given provider_id."""
        backend_mock = mock.MagicMock(provider_id=provider_id)
        strategy_mock = mock.MagicMock()
        strategy_mock.request.backend = backend_mock
        return strategy_mock

    def test_returns_none_when_user_already_set(self):
        """
        If the pipeline step already has a user, return None (no-op).
        """
        strategy = self._make_strategy()
        result = enterprise_associate_by_email(
            strategy=strategy,
            details={'email': self.user.email},
            user=self.user,
        )
        assert result is None

    def test_returns_none_when_no_email(self):
        """
        If details has no email, return None.
        """
        strategy = self._make_strategy()
        result = enterprise_associate_by_email(
            strategy=strategy,
            details={},
            user=None,
        )
        assert result is None

    def test_returns_none_when_no_matching_user(self):
        """
        If no user exists with the given email, return None.
        """
        strategy = self._make_strategy()
        result = enterprise_associate_by_email(
            strategy=strategy,
            details={'email': 'nosuchuser@example.com'},
            user=None,
        )
        assert result is None

    def test_returns_none_when_no_provider_id(self):
        """
        If the SAML provider has no provider_id, return None.
        """
        self.saml_provider_mock.provider_id = None
        strategy = self._make_strategy(provider_id=None)
        result = enterprise_associate_by_email(
            strategy=strategy,
            details={'email': self.user.email},
            user=None,
        )
        assert result is None

    def test_returns_user_when_enterprise_customer_user_matches(self):
        """
        If the email matches an existing user who is linked to the enterprise for this provider,
        delegate to social_core's associate_by_email and return the association response.
        """
        EnterpriseCustomerUser.objects.create(
            enterprise_customer=self.enterprise_customer,
            user_id=self.user.id,
        )
        strategy = self._make_strategy(provider_id='test-provider-id')
        with mock.patch('enterprise.tpa_pipeline.associate_by_email') as mock_assoc:
            mock_assoc.return_value = {'user': self.user}
            result = enterprise_associate_by_email(
                strategy=strategy,
                details={'email': self.user.email},
                user=None,
            )
        assert result == {'user': self.user}
        mock_assoc.assert_called_once()

    def test_returns_none_when_user_not_linked_to_enterprise(self):
        """
        If the email matches a user but that user is NOT an EnterpriseCustomerUser for the
        provider's enterprise, return None.
        """
        # User exists but is not linked to the enterprise customer for this IdP.
        strategy = self._make_strategy(provider_id='test-provider-id')
        result = enterprise_associate_by_email(
            strategy=strategy,
            details={'email': self.user.email},
            user=None,
        )
        assert result is None

    def test_returns_none_when_user_is_inactive(self):
        """
        If the email matches an existing user who is inactive, return None
        even if they are linked to the enterprise.
        """
        inactive_user = UserFactory(is_active=False, email='inactive@example.com')
        EnterpriseCustomerUser.objects.create(
            enterprise_customer=self.enterprise_customer,
            user_id=inactive_user.id,
        )
        strategy = self._make_strategy(provider_id='test-provider-id')
        with mock.patch('enterprise.tpa_pipeline.associate_by_email') as mock_assoc:
            mock_assoc.return_value = {'user': inactive_user}
            with mock.patch('enterprise.tpa_pipeline.log') as mock_log:
                result = enterprise_associate_by_email(
                    strategy=strategy,
                    details={'email': 'inactive@example.com'},
                    user=None,
                )
        assert result is None
        # Should log the inactive user info message.
        log_messages = [call[0][0] for call in mock_log.info.call_args_list]
        assert any(
            '[Multiple_SSO_SAML_Accounts_Association_to_User] User association account is not'
            in msg for msg in log_messages
        )

    def test_logs_exception_on_unexpected_error(self):
        """
        If an unexpected error occurs during enterprise user lookup, log the
        exception and return None.
        """
        EnterpriseCustomerUser.objects.create(
            enterprise_customer=self.enterprise_customer,
            user_id=self.user.id,
        )
        strategy = self._make_strategy(provider_id='test-provider-id')
        with mock.patch(
            'enterprise.tpa_pipeline.EnterpriseCustomerIdentityProvider.objects'
        ) as mock_objects:
            mock_objects.get.side_effect = RuntimeError('boom')
            with mock.patch('enterprise.tpa_pipeline.log') as mock_log:
                result = enterprise_associate_by_email(
                    strategy=strategy,
                    details={'email': self.user.email},
                    user=None,
                )
        assert result is None
        mock_log.exception.assert_called_once()
        assert '[Multiple_SSO_SAML_Accounts_Association_to_User]' in mock_log.exception.call_args[0][0]

    @override_settings(FEATURES={'ENABLE_ENTERPRISE_INTEGRATION': False})
    def test_returns_none_when_enterprise_disabled(self):
        """
        If ENABLE_ENTERPRISE_INTEGRATION is False, return None without
        querying enterprise models.
        """
        strategy = self._make_strategy()
        result = enterprise_associate_by_email(
            strategy=strategy,
            details={'email': self.user.email},
            user=None,
        )
        assert result is None
        # is_saml_provider should never be called when enterprise is disabled.
        self.mock_is_saml_provider.assert_not_called()

    def test_returns_none_when_associate_by_email_returns_none(self):
        """
        If the user is an enterprise customer user but associate_by_email
        returns None (e.g. multiple users with same email), return None.
        """
        EnterpriseCustomerUser.objects.create(
            enterprise_customer=self.enterprise_customer,
            user_id=self.user.id,
        )
        strategy = self._make_strategy(provider_id='test-provider-id')
        with mock.patch('enterprise.tpa_pipeline.associate_by_email') as mock_assoc:
            mock_assoc.return_value = None
            result = enterprise_associate_by_email(
                strategy=strategy,
                details={'email': self.user.email},
                user=None,
            )
        assert result is None

    def test_returns_none_for_non_saml_provider(self):
        """
        If the backend is not a SAML provider, return None without
        querying enterprise models.
        """
        self.mock_is_saml_provider.return_value = (False, None)
        strategy = self._make_strategy()
        result = enterprise_associate_by_email(
            strategy=strategy,
            details={'email': self.user.email},
            user=None,
        )
        assert result is None
