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
from enterprise.tpa_pipeline import (active_provider_enforces_data_sharing, active_provider_requests_data_sharing,
                                     get_consent_status_for_pipeline, get_ec_for_running_pipeline,
                                     get_enterprise_customer_for_request, get_enterprise_customer_for_sso,
                                     set_data_sharing_consent_record, verify_data_sharing_consent)
from enterprise.utils import NotConnectedToEdX
from test_utils.factories import EnterpriseCustomerIdentityProviderFactory, UserFactory


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
        with raises(NotConnectedToEdX) as excinfo:
            get_enterprise_customer_for_request(request)
        expected_msg = "This package must be installed in an EdX environment to look up third-party auth dependencies."
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
            assert get_ec_for_running_pipeline('pipeline') == self.customer
        with raises(NotConnectedToEdX) as excinfo:
            get_ec_for_running_pipeline('pipeline')
        expected_msg = "This package must be installed in an EdX environment to look up third-party auth dependencies."
        assert str(excinfo.value) == expected_msg

    @mock.patch('enterprise.tpa_pipeline.Registry')
    @mock.patch('enterprise.tpa_pipeline.get_pipeline_partial')
    def test_get_ec_for_null_pipeline(self, fake_pipeline, fake_registry):  # pylint: disable=unused-argument
        """
        Test that if we pass in an empty pipeline, we return early and don't try to use it.
        """
        assert get_ec_for_running_pipeline(None) is None

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
        with mock.patch('enterprise.tpa_pipeline.get_ec_for_running_pipeline') as fake_get_ec:
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
            consent.delete()
            ec_user.delete()

    def test_verify_data_sharing_consent(self):
        """
        Test that we correctly verify consent status.
        """
        backend = mock.MagicMock(name=None)
        with mock.patch('enterprise.tpa_pipeline.get_ec_for_running_pipeline') as fake_get_ec:
            fake_get_ec.return_value = None
            assert verify_data_sharing_consent(backend, self.user) is None
        with mock.patch('enterprise.tpa_pipeline.get_ec_for_running_pipeline') as fake_get_ec:
            fake_get_ec.return_value = mock.MagicMock(
                requests_data_sharing_consent=False
            )  # pylint: disable=redefined-variable-type
            assert verify_data_sharing_consent(backend, self.user) is None
        with mock.patch('enterprise.tpa_pipeline.get_ec_for_running_pipeline') as fake_get_ec:
            fake_get_ec.return_value = self.customer  # pylint: disable=redefined-variable-type
            assert isinstance(verify_data_sharing_consent(backend, self.user), HttpResponseRedirect)
            ec_user = EnterpriseCustomerUser.objects.create(
                user_id=self.user.id,  # pylint: disable=no-member
                enterprise_customer=self.customer
            )
            consent = UserDataSharingConsentAudit.objects.create(  # pylint: disable=no-member
                user=ec_user
            )
            assert isinstance(verify_data_sharing_consent(backend, self.user), HttpResponseRedirect)
            consent.state = 'enabled'
            consent.save()
            assert verify_data_sharing_consent(backend, self.user) is None
            consent.delete()
            ec_user.delete()

    def test_set_data_sharing_consent(self):
        """
        Test that the pipeline element correctly sets consent status.
        """
        backend = mock.MagicMock(name=None)
        user = self.user
        with mock.patch('enterprise.tpa_pipeline.get_ec_for_running_pipeline') as fake_get_ec:
            fake_get_ec.return_value = self.customer
            set_data_sharing_consent_record(backend, user)
            with raises(EnterpriseCustomerUser.DoesNotExist):
                EnterpriseCustomerUser.objects.get(
                    user_id=user.id,  # pylint: disable=no-member
                    enterprise_customer=self.customer
                )
            with raises(UserDataSharingConsentAudit.DoesNotExist):
                UserDataSharingConsentAudit.objects.get(
                    user__user_id=user.id,  # pylint: disable=no-member
                    user__enterprise_customer=self.customer,
                )

            set_data_sharing_consent_record(backend, user, data_sharing_consent=False)
            ec_user = EnterpriseCustomerUser.objects.get(
                user_id=user.id,  # pylint: disable=no-member
                enterprise_customer=self.customer
            )
            consent = UserDataSharingConsentAudit.objects.get(user=ec_user)
            assert not consent.enabled

            set_data_sharing_consent_record(backend, user, data_sharing_consent=True)
            ec_user = EnterpriseCustomerUser.objects.get(
                user_id=user.id,  # pylint: disable=no-member
                enterprise_customer=self.customer
            )
            consent = UserDataSharingConsentAudit.objects.get(user=ec_user)
            assert consent.enabled

            consent.delete()
            ec_user.delete()

            fake_get_ec.return_value = None  # pylint: disable=redefined-variable-type
            assert set_data_sharing_consent_record(backend, user, data_sharing_consent=True) is None
            assert UserDataSharingConsentAudit.objects.all().count() == 0
