# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` course catalogs api module.
"""

from __future__ import absolute_import, unicode_literals, with_statement

import unittest

import ddt
import mock
from edx_rest_api_client.exceptions import HttpClientError
from pytest import mark, raises

from django.contrib.auth.models import User
from django.test import RequestFactory

from enterprise.api_client.ecommerce import EcommerceApiClient
from enterprise.utils import NotConnectedToOpenEdX
from test_utils import factories


class TestEcommerceApiClientInitialization(unittest.TestCase):
    """
    Test initialization of EcommerceApiClient.
    """
    def test_raise_error_missing_course_discovery_api(self):
        message = 'To get a ecommerce_api_client, this package must be installed in an Open edX environment.'
        with raises(NotConnectedToOpenEdX) as excinfo:
            EcommerceApiClient(mock.Mock(spec=User))
        assert message == str(excinfo.value)


@ddt.ddt
@mark.django_db
class TestEcommerceApiClient(unittest.TestCase):
    """
    Test course catalog API methods.
    """

    def setUp(self):
        super(TestEcommerceApiClient, self).setUp()
        self.user = factories.UserFactory()

    def _setup_ecommerce_api_client(self, client_mock, method_name, return_value):
        """
        Sets up the E-Commerce API client
        """
        mocked_attributes = {
            method_name: mock.MagicMock(return_value=return_value),
        }
        api_mock = mock.MagicMock(**mocked_attributes)

        client_mock.return_value = api_mock

    @mock.patch('enterprise.api_client.ecommerce.ecommerce_api_client')
    def test_get_course_final_price(self, ecommerce_api_client_mock):
        mode = {
            'sku': 'verified-sku',
            'min_price': 200,
            'original_price': 500,
        }
        self._setup_ecommerce_api_client(
            client_mock=ecommerce_api_client_mock,
            method_name='baskets.calculate.get',
            return_value={
                'total_incl_tax': 100,
            }
        )
        assert EcommerceApiClient(self.user).get_course_final_price(mode) == '$100'

    @mock.patch('enterprise.api_client.ecommerce.ecommerce_api_client')
    def test_post_audit_order_to_ecommerce(self, ecommerce_api_client_mock):
        self._setup_ecommerce_api_client(
            client_mock=ecommerce_api_client_mock,
            method_name='baskets.post',
            return_value={
                'order': {
                    'number': 'ORD-071926'
                },
            }
        )
        request = RequestFactory().get('/')
        request.user = self.user
        assert EcommerceApiClient(self.user).post_audit_order_to_ecommerce(request, 'audit-sku') == 'ORD-071926'

    @mock.patch('enterprise.api_client.ecommerce.configuration_helpers')
    @mock.patch('enterprise.api_client.ecommerce.messages.error')
    @mock.patch('enterprise.api_client.ecommerce.LOGGER.error')
    @mock.patch('enterprise.api_client.ecommerce.ecommerce_api_client')
    def test_post_audit_order_to_ecommerce_error(
            self, ecommerce_api_client_mock, logger_mock, messages_mock, configuration_helpers_mock,
    ):
        product_sku = 'audit-sku'
        ecommerce_api_client_mock.return_value = mock.MagicMock(
            **{'baskets.post': mock.MagicMock(side_effect=HttpClientError)}
        )
        configuration_helpers_mock.get_value.return_value = 'test-value'

        request = RequestFactory().get('/')
        request.user = self.user

        with raises(HttpClientError):
            EcommerceApiClient(self.user).post_audit_order_to_ecommerce(request, product_sku)

        logger_mock.assert_called_with(
            'Failed to post audit enrollment of user "{usernmae}" in product "{sku}".'.format(
                usernmae=self.user.username,
                sku=product_sku,
            ),
        )
        messages_mock.assert_called_with(
            request,
            'There was an error completing your enrollment in the course, please try again. '
            'If the problem persists, contact <a href="test-value" target="_blank">test-value support</a>.'
        )
