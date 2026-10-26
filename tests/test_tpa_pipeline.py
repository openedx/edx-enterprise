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


@ddt.ddt
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

    @mock.patch('enterprise.tpa_pipeline.EnterpriseCustomerIdentityProvider.objects')
    def test_logs_exception_on_unexpected_error(self, mock_objects):
        """
        If an unexpected error occurs during enterprise user lookup, log the
        exception and return None.
        """
        EnterpriseCustomerUser.objects.create(
            enterprise_customer=self.enterprise_customer,
            user_id=self.user.id,
        )
        strategy = self._make_strategy(provider_id='test-provider-id')
        mock_objects.get.side_effect = RuntimeError('boom')
        with self.assertLogs(level='ERROR') as log_context:
            result = enterprise_associate_by_email(
                strategy=strategy,
                details={'email': self.user.email},
                user=None,
            )
        assert result is None
        assert len(log_context.records) == 1
        assert log_context.records[0].exc_info is not None
        assert '[Multiple_SSO_SAML_Accounts_Association_to_User]' in log_context.output[0]

    @ddt.data(
        # Enterprise integration disabled: returns immediately, no SAML check.
        {
            'enterprise_integration_enabled': False,
            'is_backend_a_saml_provider': True,
            'details': {'email': 'existing@example.com'},
            'expected_is_saml_provider_check_made': False,
        },
        # Backend is not a SAML provider: skip the inner enterprise lookup.
        {
            'enterprise_integration_enabled': True,
            'is_backend_a_saml_provider': False,
            'details': {'email': 'existing@example.com'},
            'expected_is_saml_provider_check_made': True,
        },
        # Details has no email key: current_user resolves to None.
        {
            'enterprise_integration_enabled': True,
            'is_backend_a_saml_provider': True,
            'details': {},
            'expected_is_saml_provider_check_made': True,
        },
        # Email does not match any existing user: current_user resolves to None.
        {
            'enterprise_integration_enabled': True,
            'is_backend_a_saml_provider': True,
            'details': {'email': 'nosuchuser@example.com'},
            'expected_is_saml_provider_check_made': True,
        },
    )
    @mock.patch('enterprise.tpa_pipeline.associate_by_email')
    def test_short_circuits_before_entering_inner_function(self, params, mock_assoc):
        """
        The outer function returns None without entering the inner enterprise
        user lookup when enterprise integration is disabled, the backend is
        not a SAML provider, or no current_user can be resolved from the
        details/user args.
        """
        if not params['is_backend_a_saml_provider']:
            self.mock_is_saml_provider.return_value = (False, None)

        strategy = self._make_strategy()

        with override_settings(ENABLE_ENTERPRISE_INTEGRATION=params['enterprise_integration_enabled']):
            # The inner function's first action is log.info(...); the absence
            # of any INFO log proves the outer function short-circuited before
            # reaching it.
            with self.assertNoLogs(level='INFO'):
                result = enterprise_associate_by_email(
                    strategy=strategy,
                    details=params['details'],
                    user=None,
                )

        assert result is None
        mock_assoc.assert_not_called()
        if params['expected_is_saml_provider_check_made']:
            self.mock_is_saml_provider.assert_called_once()
        else:
            self.mock_is_saml_provider.assert_not_called()

    @ddt.data(
        # Linked active user matched: association succeeds and is returned.
        {
            'is_user_linked_to_enterprise': True,
            'is_user_active': True,
            'associate_by_email_returns_user': True,
            'expected_returns_response': True,
            'expected_log_substring': (
                '[Multiple_SSO_SAML_Accounts_Association_to_User] User association successful'
            ),
        },
        # Linked but inactive user matched: association is rejected.
        {
            'is_user_linked_to_enterprise': True,
            'is_user_active': False,
            'associate_by_email_returns_user': True,
            'expected_returns_response': False,
            'expected_log_substring': (
                '[Multiple_SSO_SAML_Accounts_Association_to_User] User association account is not active'
            ),
        },
        # User not linked to the enterprise: try/except/else fallthrough.
        {
            'is_user_linked_to_enterprise': False,
            'is_user_active': True,
            'associate_by_email_returns_user': False,
            'expected_returns_response': False,
            'expected_log_substring': (
                '[Multiple_SSO_SAML_Accounts_Association_to_User] No user association made'
            ),
        },
        # Linked but associate_by_email returns no user (e.g. duplicate emails).
        {
            'is_user_linked_to_enterprise': True,
            'is_user_active': True,
            'associate_by_email_returns_user': False,
            'expected_returns_response': False,
            'expected_log_substring': (
                '[Multiple_SSO_SAML_Accounts_Association_to_User] No user association made'
            ),
        },
    )
    @mock.patch('enterprise.tpa_pipeline.associate_by_email')
    def test_emits_log_for_association_branch(self, params, mock_assoc):
        """
        Each non-exception branch through ``associate_by_email_if_enterprise_user``
        emits a distinguishing info log: success on active association, the
        "not active" line when the matched user is inactive, and the
        try/except/else "no association made" line for both the not-linked and
        empty-associate-response paths.
        """
        target_user = (
            self.user if params['is_user_active']
            else UserFactory(is_active=False, email='inactive@example.com')
        )
        if params['is_user_linked_to_enterprise']:
            EnterpriseCustomerUser.objects.create(
                enterprise_customer=self.enterprise_customer,
                user_id=target_user.id,
            )
        strategy = self._make_strategy(provider_id='test-provider-id')
        association_response = {'user': target_user}
        mock_assoc.return_value = (
            association_response if params['associate_by_email_returns_user'] else None
        )
        with self.assertLogs(level='INFO') as log_context:
            result = enterprise_associate_by_email(
                strategy=strategy,
                details={'email': target_user.email},
                user=None,
            )
        if params['expected_returns_response']:
            assert result == association_response
        else:
            assert result is None
        assert any(params['expected_log_substring'] in msg for msg in log_context.output)
