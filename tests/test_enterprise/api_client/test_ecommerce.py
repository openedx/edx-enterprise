"""
Tests for the `edx-enterprise` course catalogs api module.
"""

import unittest
from unittest import mock

import ddt
from pytest import mark, raises

from django.contrib import auth

from enterprise.api_client.ecommerce import EcommerceApiClient
from enterprise.utils import NotConnectedToOpenEdX
from test_utils import factories

User = auth.get_user_model()


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
        super().setUp()
        self.user = factories.UserFactory()

    @mock.patch('enterprise.api_client.ecommerce.configuration_helpers')
    @mock.patch('enterprise.api_client.ecommerce.ecommerce_api_client')
    def test_get_course_final_price(self, ecommerce_api_client_mock, *args):
        """
        Test get_course_final_price from the EcommerceAPIClient.
        """
        mode = {
            'sku': 'verified-sku',
            'min_price': 200,
            'original_price': 500,
        }
        ecommerce_api_client_mock.return_value.get.return_value.json.return_value = {'total_incl_tax': 100}
        assert EcommerceApiClient(self.user).get_course_final_price(mode) == '$100'
