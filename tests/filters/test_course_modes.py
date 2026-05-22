"""
Tests for enterprise.filters.course_modes pipeline step.
"""
import sys
import unittest
from unittest.mock import MagicMock, patch


class TestCheckoutEnterpriseContextInjector(unittest.TestCase):
    """
    Tests for CheckoutEnterpriseContextInjector pipeline step.
    """

    def _make_step(self):
        from enterprise.filters.course_modes import CheckoutEnterpriseContextInjector
        return CheckoutEnterpriseContextInjector(
            "org.openedx.learning.course_mode.checkout.started.v1",
            [],
        )

    def _run_with_patched_imports(self, enterprise_customer, context=None, request=None, course_mode=None):
        """
        Helper: run step.run_filter with deferred imports patched via sys.modules.
        """
        if context is None:
            context = {}
        if request is None:
            request = MagicMock()
        if course_mode is None:
            course_mode = MagicMock()

        step = self._make_step()

        api_mod = MagicMock()
        api_mod.enterprise_customer_for_request = MagicMock(return_value=enterprise_customer)

        with patch.dict(sys.modules, {
            'openedx': MagicMock(),
            'openedx.features': MagicMock(),
            'openedx.features.enterprise_support': MagicMock(),
            'openedx.features.enterprise_support.api': api_mod,
        }):
            return step.run_filter(context=context, request=request, course_mode=course_mode)

    def test_injects_enterprise_customer_when_found(self):
        """
        When an enterprise customer is found for the request, it is injected into the context.
        """
        enterprise_customer = {"uuid": "test-uuid", "name": "Test Enterprise"}
        context = {"course_id": "course-v1:org+course+run"}
        request = MagicMock()
        course_mode = MagicMock()

        result = self._run_with_patched_imports(
            enterprise_customer=enterprise_customer,
            context=context,
            request=request,
            course_mode=course_mode,
        )

        self.assertEqual(result["context"]["enterprise_customer"], enterprise_customer)
        self.assertIs(result["request"], request)
        self.assertIs(result["course_mode"], course_mode)

    def test_does_not_inject_when_no_enterprise_customer(self):
        """
        When no enterprise customer is found, the context is returned unchanged.
        """
        context = {"course_id": "course-v1:org+course+run"}

        result = self._run_with_patched_imports(
            enterprise_customer=None,
            context=context,
        )

        self.assertNotIn("enterprise_customer", result["context"])
        self.assertEqual(result["context"], context)

    def test_handles_exception_gracefully(self):
        """
        When enterprise_customer_for_request raises an exception, the context is returned unchanged.
        """
        step = self._make_step()
        context = {"course_id": "course-v1:org+course+run"}
        request = MagicMock()
        course_mode = MagicMock()

        api_mod = MagicMock()
        api_mod.enterprise_customer_for_request = MagicMock(side_effect=Exception("Connection error"))

        with patch.dict(sys.modules, {
            'openedx': MagicMock(),
            'openedx.features': MagicMock(),
            'openedx.features.enterprise_support': MagicMock(),
            'openedx.features.enterprise_support.api': api_mod,
        }):
            result = step.run_filter(context=context, request=request, course_mode=course_mode)

        self.assertNotIn("enterprise_customer", result["context"])
        self.assertEqual(result["context"], context)
