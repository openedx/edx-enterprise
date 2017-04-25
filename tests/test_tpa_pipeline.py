# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` tpa-pipeline module.
"""
from __future__ import absolute_import, unicode_literals

import unittest

import mock
from pytest import mark, raises

from django.http import HttpResponseRedirect

from enterprise.models import EnterpriseCustomer, EnterpriseCustomerUser, UserDataSharingConsentAudit

from enterprise.tpa_pipeline import (
    active_provider_enforces_data_sharing,
    active_provider_requests_data_sharing,
    get_consent_status_for_pipeline,
    get_enterprise_customer_for_running_pipeline,
    get_enterprise_customer_for_request,
    get_enterprise_customer_for_sso,
    handle_enterprise_logistration,
)
from enterprise.utils import NotConnectedToOpenEdx
from test_utils.factories import EnterpriseCustomerFactory, EnterpriseCustomerIdentityProviderFactory, UserFactory


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

    @mock.patch('enterprise.tpa_pipeline.get_pipeline_partial')
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
        with raises(NotConnectedToOpenEdx) as excinfo:
            get_enterprise_customer_for_request(request)
        expected_msg = "This package must be installed in an Open edX " \
                       "environment to look up third-party auth dependencies."
        assert str(excinfo.value) == expected_msg

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

    @mock.patch('enterprise.tpa_pipeline.get_pipeline_partial')
    def test_get_ec_for_pipeline(self, fake_pipeline):
        """
        Test that we get the correct enterprise custoemr for a given running pipeline.
        """
        fake_pipeline.return_value = {'kwargs': {'access_token': 'dummy'}, 'backend': 'fake_backend'}
        with mock.patch('enterprise.tpa_pipeline.Registry') as fake_registry:
            provider = mock.MagicMock(provider_id='provider_slug')
            fake_registry.get_from_pipeline.return_value = provider
            assert get_enterprise_customer_for_running_pipeline('pipeline') == self.customer
        with raises(NotConnectedToOpenEdx) as excinfo:
            get_enterprise_customer_for_running_pipeline('pipeline')
        expected_msg = "This package must be installed in an Open edX " \
                       "environment to look up third-party auth dependencies."
        assert str(excinfo.value) == expected_msg

    @mock.patch('enterprise.tpa_pipeline.Registry')
    @mock.patch('enterprise.tpa_pipeline.get_pipeline_partial')
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
            fake_ec_getter.return_value = False  # pylint: disable=redefined-variable-type
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
            fake_ec_getter.return_value = False  # pylint: disable=redefined-variable-type
            assert not active_provider_requests_data_sharing(request)
            fake_ec = mock.MagicMock()
            fake_ec.requests_data_sharing_consent = False
            fake_ec_getter.return_value = fake_ec  # pylint: disable=redefined-variable-type
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
        backend = mock.MagicMock(name=None)
        with mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_running_pipeline') as fake_get_ec:
            fake_get_ec.return_value = None
            assert verify_data_sharing_consent(backend, self.user) is None
        with mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_running_pipeline') as fake_get_ec:
            fake_get_ec.return_value = mock.MagicMock(
                requests_data_sharing_consent=False
            )  # pylint: disable=redefined-variable-type
            assert verify_data_sharing_consent(backend, self.user) is None
        with mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_running_pipeline') as fake_get_ec:
            fake_get_ec.return_value = self.customer  # pylint: disable=redefined-variable-type
            assert isinstance(verify_data_sharing_consent(backend, self.user), HttpResponseRedirect)

    def test_handle_enterprise_logistration_consent_not_required(self):
        """
        Test that when consent isn't required, we create an EnterpriseCustomerUser, then return.
        """
        backend = mock.MagicMock(name=None)
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

    def test_handle_enterprise_logistration_consent_not_required_for_existing_enterprise_user(self):
        """
        Test that when consent isn't required and learner is already linked,
        we simply return the exi    sting EnterpriseCustomerUser.
        """
        backend = mock.MagicMock(name=None)
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

    def test_handle_enterprise_logistration_consent_required(self):
        """
        Test that when consent is required, we redirect to the consent page.
        """
        backend = mock.MagicMock(name=None)
        with mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_running_pipeline') as fake_get_ec:
            fake_get_ec.return_value = self.customer
            assert isinstance(handle_enterprise_logistration(backend, self.user), HttpResponseRedirect)

    def test_handle_enterprise_logistration_consent_optional(self):
        """
        Test that when consent is optional, but requested, we redirect to the consent page.
        """
        backend = mock.MagicMock(name=None)
        with mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_running_pipeline') as fake_get_ec:
            self.customer.enforce_data_sharing_consent = EnterpriseCustomer.DATA_CONSENT_OPTIONAL
            fake_get_ec.return_value = self.customer
            assert isinstance(handle_enterprise_logistration(backend, self.user), HttpResponseRedirect)

    def test_handle_enterprise_logistration_consent_required_at_enrollment(self):
        """
        Test that when consent is required at enrollment, but optional at logistration, we redirect to the consent page.
        """
        backend = mock.MagicMock(name=None)
        with mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_running_pipeline') as fake_get_ec:
            self.customer.enforce_data_sharing_consent = EnterpriseCustomer.AT_ENROLLMENT
            fake_get_ec.return_value = self.customer
            assert isinstance(handle_enterprise_logistration(backend, self.user), HttpResponseRedirect)

    def test_handle_enterprise_logistration_consent_previously_declined(self):
        """
        Test that when consent has been previously been declined, we redirect to the consent page.
        """
        backend = mock.MagicMock(name=None)
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
        backend = mock.MagicMock(name=None)
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
