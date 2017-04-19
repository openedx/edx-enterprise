# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` Ecommerce API module.
"""

from __future__ import absolute_import, unicode_literals, with_statement


import unittest

import mock

from django.contrib.auth.models import User

from enterprise.ecommerce_api import EcommerceApiClient


class TestEcommerceApiClientInitialization(unittest.TestCase):
    """
    Test the setup process for building an EcommerceApiClient instance.
    """

    @mock.patch('enterprise.ecommerce_api.ecommerce_api_client')
    def test_init_not_configured(self, _):
        client = EcommerceApiClient(mock.MagicMock(spec=User))
        assert client.client is None

    def test_init_no_client(self):
        client = EcommerceApiClient(mock.MagicMock(spec=User))
        assert client.client is None

    @mock.patch('enterprise.ecommerce_api.ecommerce_api_client')
    @mock.patch('enterprise.ecommerce_api.is_commerce_service_configured')
    def test_init_configured(self, mock_is_configured, mock_api_client):
        mock_is_configured.return_value = True
        resulting_api_client_singleton = object()
        mock_api_client.return_value = resulting_api_client_singleton
        client = EcommerceApiClient(mock.MagicMock(spec=User))
        assert client.client is resulting_api_client_singleton


class TestEcommerceApiClientBehavior(unittest.TestCase):
    """
    Test the behavior of getting coupons, both by ID and as a set.
    """

    def setUp(self):
        self.subclient = mock.MagicMock()
        with mock.patch('enterprise.ecommerce_api.ecommerce_api_client') as client_getter:
            client_getter.return_value = self.subclient
            with mock.patch('enterprise.ecommerce_api.is_commerce_service_configured') as is_configured:
                is_configured.return_value = True
                self.client = EcommerceApiClient(mock.MagicMock(spec=User))
        self.id_getter = self.subclient.coupons
        self.get_single_coupon_mock = self.subclient.coupons.return_value.get
        self.get_multiple_coupons_mock = self.subclient.coupons.get
        super(TestEcommerceApiClientBehavior, self).setUp()

    def test_single_coupon(self):
        self.get_single_coupon_mock.return_value = {
            'response': 'value'
        }
        response = self.client.get_single_coupon(123)
        assert response == {'response': 'value'}
        self.get_single_coupon_mock.assert_called_once()
        self.id_getter.assert_called_once_with(123)

    def test_single_coupon_fails(self):
        self.get_single_coupon_mock.side_effect = ValueError
        response = self.client.get_single_coupon(123)
        assert response == {}
        self.get_single_coupon_mock.assert_called_once()
        self.id_getter.assert_called_once_with(123)

    def test_single_coupon_no_client(self):
        self.client.client = None
        response = self.client.get_single_coupon(123)
        assert response == {}

    def test_get_multiple_coupons(self):
        self.get_multiple_coupons_mock.side_effect = [
            {"results": [1, 2, 3], "next": "url"},
            {"results": [4, 5, 6]},
            {"results": [7, 8, 9]}
        ]
        response = self.client.get_coupons_by_enterprise_customer('123-456-789-ABC-DEF-0')
        assert response == [1, 2, 3, 4, 5, 6]
        self.get_multiple_coupons_mock.assert_has_calls(
            [
                mock.call(enterprise_customer='123-456-789-ABC-DEF-0', page=1),
                mock.call(enterprise_customer='123-456-789-ABC-DEF-0', page=2),
            ]
        )

    def test_get_multiple_coupons_error_partway_through(self):
        self.get_multiple_coupons_mock.side_effect = [
            {"results": [1, 2, 3], "next": "url"},
            ValueError,
            {"results": [7, 8, 9]}
        ]
        response = self.client.get_coupons_by_enterprise_customer('123-456-789-ABC-DEF-0')
        assert response == [1, 2, 3]
        self.get_multiple_coupons_mock.assert_has_calls(
            [
                mock.call(enterprise_customer='123-456-789-ABC-DEF-0', page=1),
                mock.call(enterprise_customer='123-456-789-ABC-DEF-0', page=2),
            ]
        )

    def test_get_multiple_coupons_error_at_beginning(self):
        self.get_multiple_coupons_mock.side_effect = ValueError
        response = self.client.get_coupons_by_enterprise_customer('123-456-789-ABC-DEF-0')
        assert response == []
        self.get_multiple_coupons_mock.assert_has_calls(
            [
                mock.call(enterprise_customer='123-456-789-ABC-DEF-0', page=1),
            ]
        )

    def test_get_multiple_coupons_no_client(self):
        self.client.client = None
        response = self.client.get_coupons_by_enterprise_customer('123-456-789-ABC-DEF-0')
        assert response == []
