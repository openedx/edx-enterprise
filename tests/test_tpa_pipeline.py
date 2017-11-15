# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` tpa-pipeline module.
"""
from __future__ import absolute_import, unicode_literals

import unittest

import ddt
import mock
from pytest import mark

from django.contrib.messages.storage import fallback
from django.contrib.sessions.backends import cache
from django.test import RequestFactory

from enterprise.models import EnterpriseCustomerUser
from enterprise.tpa_pipeline import get_enterprise_customer_for_running_pipeline, handle_enterprise_logistration
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
        self.request_factory = RequestFactory()
        self.request = self.request_factory.get('/')
        self.request.session = cache.SessionStore()
        super(TestTpaPipeline, self).setUp()

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
            enterprise_customer = EnterpriseCustomerFactory(
                enable_data_sharing_consent=False
            )
            fake_get_ec.return_value = enterprise_customer
            assert handle_enterprise_logistration(backend, self.user) is None
            assert EnterpriseCustomerUser.objects.filter(
                enterprise_customer=enterprise_customer,
                user_id=self.user.id
            ).count() == 1

    def test_handle_enterprise_logistration_not_user_linking(self):
        """
        Test if there is not any enterprise customer then EnterpriseCustomerUser would not be associated with it.
        """
        backend = self.get_mocked_sso_backend()
        self.user = UserFactory()
        with mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_running_pipeline') as fake_get_ec:
            enterprise_customer = EnterpriseCustomerFactory(
                enable_data_sharing_consent=False
            )
            fake_get_ec.return_value = None
            assert handle_enterprise_logistration(backend, self.user) is None
            assert EnterpriseCustomerUser.objects.filter(
                enterprise_customer=enterprise_customer,
                user_id=self.user.id
            ).count() == 0

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
