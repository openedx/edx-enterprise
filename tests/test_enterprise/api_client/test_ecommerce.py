"""
Tests for the `edx-enterprise` course catalogs api module.
"""
import logging
import unittest
from unittest import mock

import ddt
from pytest import mark, raises
from requests.exceptions import ConnectionError, RequestException, Timeout  # pylint: disable=redefined-builtin

from django.contrib import auth

from enterprise.api_client.ecommerce import EcommerceApiClient
from enterprise.utils import NotConnectedToOpenEdX
from test_utils import MockLoggingHandler, factories

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
    @mock.patch('enterprise.api_client.ecommerce.get_ecommerce_api_client')
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

    @mock.patch('enterprise.api_client.ecommerce.configuration_helpers')
    @mock.patch('enterprise.api_client.ecommerce.get_ecommerce_api_client')
    @ddt.data(RequestException, Timeout, ConnectionError)
    def test_create_manual_enrollment_orders_error(self, exception, ecommerce_api_client_mock, *args):
        """
        Test create_manual_enrollment_orders error handling from the EcommerceAPIClient.
        """
        client = EcommerceApiClient(self.user)
        ecommerce_api_client_mock.return_value.post.side_effect = exception

        logger = logging.getLogger('enterprise.api_client.ecommerce')
        handler = MockLoggingHandler(level="ERROR")
        logger.addHandler(handler)

        enrollments = {'fake_enrollmetn': 'fake_content'}
        client.create_manual_enrollment_orders(enrollments)

        expected_message = (
            "Failed to create order for manual enrollments for the following enrollments: "
            f"{enrollments}. Reason: {str(exception())}"
        )

        assert handler.messages['error'][0] == expected_message
