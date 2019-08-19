# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` course catalogs api module.
"""

from __future__ import absolute_import, unicode_literals, with_statement

import unittest

import ddt
import mock
from pytest import mark, raises
from requests.exceptions import Timeout

from django.conf import settings
from django.contrib.auth.models import User

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
        self.ecommerce_service_user = factories.UserFactory(username=settings.ECOMMERCE_SERVICE_WORKER_USERNAME)

    def _setup_ecommerce_api_client(self, client_mock, method_name, return_value, side_effect=None):
        """
        Sets up the E-Commerce API client
        """
        mocked_attributes = {
            method_name: mock.MagicMock(return_value=return_value, side_effect=side_effect),
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
    def test_create_ecommerce_order_for_manual_course_enrollment_post_success(self, ecommerce_api_client_mock):
        """
        Test that `create_ecommerce_order_for_manual_course_enrollment` returns expected response in case of success.
        """
        return_value = {'order_number': 'EDX-100100'}
        self._setup_ecommerce_api_client(
            client_mock=ecommerce_api_client_mock,
            method_name='manual_course_enrollment_order.post',
            return_value=return_value
        )
        assert EcommerceApiClient().create_ecommerce_order_for_manual_course_enrollment(1, '', '', '') == return_value

    @mock.patch('enterprise.api_client.ecommerce.ecommerce_api_client')
    def test_create_ecommerce_order_for_manual_course_enrollment_post_fail(self, ecommerce_api_client_mock):
        """
        Test that `create_ecommerce_order_for_manual_course_enrollment` returns expected response in case of exception.
        """
        self._setup_ecommerce_api_client(
            client_mock=ecommerce_api_client_mock,
            method_name='manual_course_enrollment_order.post',
            return_value={},
            side_effect=Timeout()
        )

        with mock.patch('enterprise.api_client.ecommerce.LOGGER.exception') as mock_logger:
            assert EcommerceApiClient().create_ecommerce_order_for_manual_course_enrollment(
                1, 'bat', 'bat@example.com', 'course-v1:HarvardX+CoolScience+2016'
            ) is None
            assert mock_logger.called
