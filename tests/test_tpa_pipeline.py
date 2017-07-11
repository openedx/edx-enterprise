# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` tpa-pipeline module.
"""
from __future__ import absolute_import, unicode_literals

import unittest

import ddt
import mock
from pytest import mark

from django.contrib import messages
from django.contrib.messages.storage import fallback
from django.contrib.sessions.backends import cache
from django.http import HttpResponseRedirect
from django.test import RequestFactory

from enterprise.models import EnterpriseCustomer, EnterpriseCustomerUser, UserDataSharingConsentAudit
from enterprise.tpa_pipeline import (
    active_provider_enforces_data_sharing,
    active_provider_requests_data_sharing,
    get_consent_status_for_pipeline,
    get_enterprise_customer_for_request,
    get_enterprise_customer_for_running_pipeline,
    get_enterprise_customer_for_sso,
    handle_enterprise_logistration,
)
from enterprise.utils import NotConnectedToOpenEdX
from test_utils.factories import EnterpriseCustomerFactory, EnterpriseCustomerIdentityProviderFactory, UserFactory


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
        super(TestTpaPipeline, self).setUp()

    def get_mocked_sso_backend(self):
        """
        Get a mocked request backend with mocked strategy.
        """
        request_factory = RequestFactory()
        request = request_factory.get('/')
        request.session = cache.SessionStore()
        # Monkey-patch storage for messaging;   pylint: disable=protected-access
        request._messages = fallback.FallbackStorage(request)

        strategy_mock = mock.MagicMock(request=request)
        backend = mock.MagicMock(
            name=None,
            strategy=strategy_mock,
        )
        return backend

    def _assert_request_message(self, request_message, expected_message_tags, expected_message_text):
        """
        Verify the request message tags and text.
        """
        self.assertEqual(request_message.tags, expected_message_tags)
        self.assertEqual(request_message.message, expected_message_text)

    def _assert_enterprise_linking_messages(self, request, user_is_active=True):
        """
        Verify request messages for a learner when he/she is linked with an
        enterprise depending on whether the learner has activated the linked
        account.
        """
        request_messages = [msg for msg in messages.get_messages(request)]
        if user_is_active:
            # Verify that request contains the expected success message when a
            # learner with activated account is linked with an enterprise
            self.assertEqual(len(request_messages), 1)
            self._assert_request_message(
                request_messages[0],
                'success',
                '<span>Account created</span> Thank you for creating an account with edX.'
            )
        else:
            # Verify that request contains the expected success message and an
            # info message when a learner with unactivated account is linked
            # with an enterprise.
            self.assertEqual(len(request_messages), 2)
            self._assert_request_message(
                request_messages[0],
                'success',
                '<span>Account created</span> Thank you for creating an account with edX.'
            )
            self._assert_request_message(
                request_messages[1],
                'info',
                '<span>Activate your account</span> Check your inbox for an activation email. '
                'You will not be able to log back into your account until you have activated it.'
            )

    @mock.patch('enterprise.tpa_pipeline.get_partial_pipeline')
    def test_get_ec_for_request(self, fake_pipeline):
        """
        Test that get_ec_for_request works.
        """
        request = mock.MagicMock()
        fake_provider = mock.MagicMock()
        fake_provider.provider_id = 'provider_slug'
        fake_pipeline.return_value = {'kwargs': {'access_token': 'dummy'}, 'backend': 'fake_backend'}
        with mock.patch('enterprise.tpa_pipeline.Registry') as fake_registry:
            fake_registry.get_from_pipeline.return_value = fake_provider
            assert get_enterprise_customer_for_request(request) == self.customer
        with self.assertRaises(NotConnectedToOpenEdX):
            get_enterprise_customer_for_request(request)

    def test_get_ec_for_sso(self):
        """
        Test that we get the correct enterprise customer for a given SSO provider.
        """
        provider = mock.MagicMock(provider_id='provider_slug')
        assert get_enterprise_customer_for_sso(provider) == self.customer
        assert get_enterprise_customer_for_sso(None) is None
        with mock.patch('enterprise.tpa_pipeline.EnterpriseCustomer.objects.get') as get_mock:
            get_mock.side_effect = EnterpriseCustomer.DoesNotExist
            assert get_enterprise_customer_for_sso(provider) is None

    @mock.patch('enterprise.tpa_pipeline.get_partial_pipeline')
    def test_get_ec_for_pipeline(self, fake_pipeline):
        """
        Test that we get the correct enterprise custoemr for a given running pipeline.
        """
        fake_pipeline.return_value = {'kwargs': {'access_token': 'dummy'}, 'backend': 'fake_backend'}
        with mock.patch('enterprise.tpa_pipeline.Registry') as fake_registry:
            provider = mock.MagicMock(provider_id='provider_slug')
            fake_registry.get_from_pipeline.return_value = provider
            assert get_enterprise_customer_for_running_pipeline('pipeline') == self.customer
        with self.assertRaises(NotConnectedToOpenEdX):
            get_enterprise_customer_for_running_pipeline('pipeline')

    @mock.patch('enterprise.tpa_pipeline.Registry')
    @mock.patch('enterprise.tpa_pipeline.get_partial_pipeline')
    def test_get_ec_for_null_pipeline(self, fake_pipeline, fake_registry):  # pylint: disable=unused-argument
        """
        Test that if we pass in an empty pipeline, we return early and don't try to use it.
        """
        assert get_enterprise_customer_for_running_pipeline(None) is None

    def test_active_provider_enforces_data_sharing(self):
        """
        Test that we can correctly check whether data sharing is enforced.
        """
        request = mock.MagicMock(session={'partial_pipeline_token': True})
        with mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request') as fake_ec_getter:
            fake_ec_getter.return_value = self.customer
            assert active_provider_enforces_data_sharing(request, EnterpriseCustomer.AT_LOGIN)
            fake_ec_getter.return_value = False
            assert not active_provider_enforces_data_sharing(request, EnterpriseCustomer.AT_LOGIN)
            request.session = {}
            assert not active_provider_enforces_data_sharing(request, EnterpriseCustomer.AT_LOGIN)

    def test_active_provider_requests_data_sharing(self):
        """
        Test that we can correctly check whether data sharing is requested.
        """
        request = mock.MagicMock(session={'partial_pipeline_token': True})
        with mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request') as fake_ec_getter:
            fake_ec_getter.return_value = self.customer
            assert active_provider_requests_data_sharing(request)
            fake_ec_getter.return_value = False
            assert not active_provider_requests_data_sharing(request)
            fake_ec = mock.MagicMock()
            fake_ec.requests_data_sharing_consent = False
            fake_ec_getter.return_value = fake_ec
            assert not active_provider_requests_data_sharing(request)
            request.session = {}
            assert not active_provider_requests_data_sharing(request)

    def test_get_consent_status(self):
        """
        Test that we can get the correct consent status.
        """
        with mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_running_pipeline') as fake_get_ec:
            fake_get_ec.return_value = self.customer
            pipeline = mock.MagicMock(kwargs={'user': self.user})
            assert get_consent_status_for_pipeline(pipeline) is None
            ec_user = EnterpriseCustomerUser.objects.create(
                user_id=self.user.id,  # pylint: disable=no-member
                enterprise_customer=self.customer
            )
            consent = UserDataSharingConsentAudit.objects.create(  # pylint: disable=no-member
                user=ec_user
            )
            assert get_consent_status_for_pipeline(pipeline) == consent

    def test_handle_enterprise_logistration_no_pipeline(self):
        """
        Test that when there's no pipeline, we do nothing, then return.
        """
        backend = self.get_mocked_sso_backend()
        with mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_running_pipeline') as fake_get_ec:
            fake_get_ec.return_value = None
            assert handle_enterprise_logistration(backend, self.user) is None
            assert EnterpriseCustomerUser.objects.count() == 0

    @mock.patch('enterprise.tpa_pipeline.configuration_helpers')
    @ddt.data(False, True)
    def test_handle_enterprise_logistration_consent_not_required(
            self,
            user_is_active,
            configuration_helpers_mock,
    ):
        """
        Test that when consent isn't required, we create an EnterpriseCustomerUser, then return.
        """
        configuration_helpers_mock.get_value.return_value = 'edX'
        backend = self.get_mocked_sso_backend()
        self.user = UserFactory(is_active=user_is_active)
        with mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_running_pipeline') as fake_get_ec:
            enterprise_customer = EnterpriseCustomerFactory(
                enable_data_sharing_consent=False
            )
            fake_get_ec.return_value = enterprise_customer
            assert handle_enterprise_logistration(backend, self.user) is None
            assert EnterpriseCustomerUser.objects.filter(
                enterprise_customer=enterprise_customer,
                user_id=self.user.id
            ).count() == 1
            assert UserDataSharingConsentAudit.objects.filter(
                user__user_id=self.user.id,
                user__enterprise_customer=enterprise_customer,
            ).count() == 0

            # Now verify that request contains the expected messages when a
            # learner is linked with an enterprise
            self._assert_enterprise_linking_messages(backend.strategy.request, user_is_active)

    @mock.patch('enterprise.tpa_pipeline.configuration_helpers')
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_running_pipeline')
    def test_handle_enterprise_logistration_consent_externally_managed(
            self,
            fake_get_ec,
            configuration_helpers_mock,
    ):
        """
        Test that when consent is externally managed, we create an EnterpriseCustomerUser and
        UserDataSharingConsentAudit object, then return.
        """
        configuration_helpers_mock.get_value.return_value = 'edX'
        backend = self.get_mocked_sso_backend()
        enterprise_customer = EnterpriseCustomerFactory(
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent=EnterpriseCustomer.EXTERNALLY_MANAGED
        )
        fake_get_ec.return_value = enterprise_customer
        assert handle_enterprise_logistration(backend, self.user) is None
        assert EnterpriseCustomerUser.objects.filter(
            enterprise_customer=enterprise_customer,
            user_id=self.user.id
        ).count() == 1
        assert UserDataSharingConsentAudit.objects.filter(
            user__user_id=self.user.id,
            user__enterprise_customer=enterprise_customer,
            state=UserDataSharingConsentAudit.EXTERNALLY_MANAGED
        ).count() == 1

    @mock.patch('enterprise.tpa_pipeline.configuration_helpers')
    def test_handle_enterprise_logistration_consent_not_required_for_existing_enterprise_user(
            self,
            configuration_helpers_mock,
    ):
        """
        Test that when consent isn't required and learner is already linked,
        we simply return the existing EnterpriseCustomerUser.
        """
        configuration_helpers_mock.get_value.return_value = 'edX'
        backend = self.get_mocked_sso_backend()
        with mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_running_pipeline') as fake_get_ec:
            enterprise_customer = EnterpriseCustomerFactory(
                enable_data_sharing_consent=False
            )
            fake_get_ec.return_value = enterprise_customer

            # manually link the user with the enterprise
            EnterpriseCustomerUser.objects.create(
                enterprise_customer=enterprise_customer,
                user_id=self.user.id
            )

            assert handle_enterprise_logistration(backend, self.user) is None
            assert EnterpriseCustomerUser.objects.filter(
                enterprise_customer=enterprise_customer,
                user_id=self.user.id
            ).count() == 1
            assert UserDataSharingConsentAudit.objects.filter(
                user__user_id=self.user.id,
                user__enterprise_customer=enterprise_customer,
            ).count() == 0

    def test_handle_enterprise_logistration_consent_required_at_login(self):
        """
        Test that when consent is required at login, we redirect to the consent page on login.
        """
        backend = self.get_mocked_sso_backend()
        with mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_running_pipeline') as fake_get_ec:
            self.customer.enforce_data_sharing_consent = EnterpriseCustomer.AT_LOGIN
            fake_get_ec.return_value = self.customer
            assert isinstance(handle_enterprise_logistration(backend, self.user), HttpResponseRedirect)

    @mock.patch('enterprise.tpa_pipeline.configuration_helpers')
    @ddt.data(EnterpriseCustomer.DATA_CONSENT_OPTIONAL,
              EnterpriseCustomer.AT_ENROLLMENT,
              EnterpriseCustomer.EXTERNALLY_MANAGED)
    def test_handle_enterprise_logistration_consent_not_required_at_login(
            self,
            enforce_data_sharing_consent,
            configuration_helpers_mock,
    ):
        """
        Test that when consent is requested, but not required at login, we do not redirect to the consent page on login.
        """
        configuration_helpers_mock.get_value.return_value = 'edX'
        backend = self.get_mocked_sso_backend()
        with mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_running_pipeline') as fake_get_ec:
            self.customer.enforce_data_sharing_consent = enforce_data_sharing_consent
            fake_get_ec.return_value = self.customer
            assert handle_enterprise_logistration(backend, self.user) is None

    def test_handle_enterprise_logistration_consent_previously_declined(self):
        """
        Test that when consent has been previously been declined, we redirect to the consent page.
        """
        backend = self.get_mocked_sso_backend()
        with mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_running_pipeline') as fake_get_ec:
            fake_get_ec.return_value = self.customer
            ec_user = EnterpriseCustomerUser.objects.create(
                user_id=self.user.id,  # pylint: disable=no-member
                enterprise_customer=self.customer
            )
            UserDataSharingConsentAudit.objects.create(  # pylint: disable=no-member
                user=ec_user
            )
            assert isinstance(handle_enterprise_logistration(backend, self.user), HttpResponseRedirect)

    def test_handle_enterprise_logistration_consent_provided(self):
        """
        Test that when consent has been provided, we return and allow the pipeline to proceed.
        """
        backend = self.get_mocked_sso_backend()
        with mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_running_pipeline') as fake_get_ec:
            fake_get_ec.return_value = self.customer
            ec_user = EnterpriseCustomerUser.objects.create(
                user_id=self.user.id,  # pylint: disable=no-member
                enterprise_customer=self.customer
            )
            UserDataSharingConsentAudit.objects.create(  # pylint: disable=no-member
                user=ec_user,
                state='enabled',
            )
            assert handle_enterprise_logistration(backend, self.user) is None
