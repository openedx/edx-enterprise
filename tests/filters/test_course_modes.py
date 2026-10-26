"""
Tests for enterprise.filters.course_modes pipeline step.
"""
import unittest
from unittest.mock import MagicMock, patch

import ddt
import pytest

from django.test.client import RequestFactory

from enterprise.filters.course_modes import CalculateEnterpriseDiscountedPrice
from test_utils.factories import UserFactory


@ddt.ddt
class TestCalculateEnterpriseDiscountedPrice(unittest.TestCase):
    """
    Tests for CalculateEnterpriseDiscountedPrice pipeline step.
    """

    def _make_request(self):
        return RequestFactory().get('/')

    def _make_step(self):
        return CalculateEnterpriseDiscountedPrice(
            "org.openedx.learning.course_mode.price.requested.v1",
            [],
        )

    @ddt.data(
        {
            'description': 'overrides_price_when_enterprise_customer_and_sku_present',
            'current_request': True,
            'enterprise_customer': {"uuid": "test-uuid", "name": "Test Enterprise"},
            'customer_side_effect': None,
            'sku': 'test-sku',
            'final_price': 42,
            'expected_price': 42,
        },
        {
            'description': 'no_enterprise_customer',
            'current_request': True,
            'enterprise_customer': None,
            'customer_side_effect': None,
            'sku': 'test-sku',
            'final_price': None,
            'expected_price': 100,
        },
        {
            'description': 'no_sku',
            'current_request': True,
            'enterprise_customer': {"uuid": "test-uuid", "name": "Test Enterprise"},
            'customer_side_effect': None,
            'sku': None,
            'final_price': None,
            'expected_price': 100,
        },
        {
            'description': 'no_current_request',
            'current_request': False,
            'enterprise_customer': None,
            'customer_side_effect': None,
            'sku': 'test-sku',
            'final_price': None,
            'expected_price': 100,
        },

    )
    @ddt.unpack
    @pytest.mark.django_db
    @patch('enterprise.filters.course_modes.get_course_final_price')
    @patch('enterprise.filters.course_modes.enterprise_customer_for_request')
    @patch('enterprise.filters.course_modes.get_current_request')
    def test_run_filter_price(
        self,
        mock_get_current_request,
        mock_get_customer,
        mock_get_final_price,
        description,  # pylint: disable=W0613
        current_request,
        enterprise_customer,
        customer_side_effect,
        sku,
        final_price,
        expected_price,
    ):
        """
        Verifies the price is overridden with the enterprise discounted price when an
        enterprise customer and SKU are present, and left unchanged otherwise.
        """
        mock_get_current_request.return_value = self._make_request() if current_request else None
        mock_get_customer.return_value = enterprise_customer
        mock_get_customer.side_effect = customer_side_effect
        mock_get_final_price.return_value = final_price

        user = UserFactory()
        course_mode_data = MagicMock(sku=sku)
        result = self._make_step().run_filter(user=user, course_mode_data=course_mode_data, price=100.00)

        assert result["price"] == expected_price
