"""
Tests for enterprise.filters.course_modes pipeline step.
"""
import unittest
from unittest.mock import MagicMock, patch

from requests.exceptions import HTTPError

from django.test.client import RequestFactory

from enterprise.filters.course_modes import CheckoutEnterpriseContextInjector


class TestCheckoutEnterpriseContextInjector(unittest.TestCase):
    """
    Tests for CheckoutEnterpriseContextInjector pipeline step.
    """

    def _make_request(self):
        request = RequestFactory().get('/')
        return request

    @patch('enterprise.filters.course_modes.enterprise_customer_for_request')
    def test_injects_enterprise_customer_when_found(self, mock_get_customer):
        """
        When an enterprise customer is found for the request, it is injected into the context.
        """
        enterprise_customer = {"uuid": "test-uuid", "name": "Test Enterprise"}
        mock_get_customer.return_value = enterprise_customer

        step = CheckoutEnterpriseContextInjector(
            "org.openedx.learning.course_mode.checkout.started.v1",
            [],
        )
        result = step.run_filter(
            context={"course_id": "course-v1:org+course+run"},
            request=self._make_request(),
            course_mode=MagicMock(),
        )

        self.assertEqual(result["context"]["enterprise_customer"], enterprise_customer)

    @patch('enterprise.filters.course_modes.enterprise_customer_for_request')
    def test_does_not_inject_when_no_enterprise_customer(self, mock_get_customer):
        """
        When no enterprise customer is found, the context is returned unchanged.
        """
        mock_get_customer.return_value = None

        step = CheckoutEnterpriseContextInjector(
            "org.openedx.learning.course_mode.checkout.started.v1",
            [],
        )
        context = {"course_id": "course-v1:org+course+run"}
        result = step.run_filter(
            context=context,
            request=self._make_request(),
            course_mode=MagicMock(),
        )

        self.assertNotIn("enterprise_customer", result["context"])
        self.assertEqual(result["context"], context)

    @patch('enterprise.filters.course_modes.enterprise_customer_for_request')
    def test_handles_exception_gracefully(self, mock_get_customer):
        """
        When enterprise_customer_for_request raises an exception, the context is returned unchanged.
        """
        mock_get_customer.side_effect = HTTPError("Error")

        step = CheckoutEnterpriseContextInjector(
            "org.openedx.learning.course_mode.checkout.started.v1",
            [],
        )
        context = {"course_id": "course-v1:org+course+run"}
        result = step.run_filter(
            context=context,
            request=self._make_request(),
            course_mode=MagicMock(),
        )

        self.assertNotIn("enterprise_customer", result["context"])
        self.assertEqual(result["context"], context)
