"""
Unit tests for enterprise.filters.logistration pipeline steps.
"""
import sys
import unittest
from unittest.mock import MagicMock, patch


class TestLogistrationContextEnricher(unittest.TestCase):
    """
    Tests for the LogistrationContextEnricher pipeline step.
    """

    def _get_step(self):
        from enterprise.filters.logistration import LogistrationContextEnricher
        return LogistrationContextEnricher('test-filter', {})

    def test_run_filter_no_enterprise_customer(self):
        """
        Context is returned unchanged when no enterprise customer is found.
        """
        step = self._get_step()
        request = MagicMock()
        context = {'data': {'some_key': 'some_value'}}

        result = self._run_with_patched_imports(
            step,
            context=context,
            request=request,
            enterprise_customer=None,
        )

        self.assertEqual(result['context'], context)
        self.assertEqual(result['request'], request)

    def _run_with_patched_imports(self, step, context, request, enterprise_customer):
        """
        Helper: run step.run_filter with deferred imports patched.
        """
        mock_ecfr = MagicMock(return_value=enterprise_customer)
        mock_update = MagicMock()
        mock_get_slug = MagicMock(return_value='https://example.com/slug-login/')

        # Install fake openedx modules into sys.modules so deferred imports succeed
        enterprise_support_api_mod = MagicMock()
        enterprise_support_api_mod.enterprise_customer_for_request = mock_ecfr

        enterprise_support_utils_mod = MagicMock()
        enterprise_support_utils_mod.update_logistration_context_for_enterprise = mock_update
        enterprise_support_utils_mod.get_enterprise_slug_login_url = mock_get_slug
        enterprise_support_utils_mod.handle_enterprise_cookies_for_logistration = MagicMock()

        with patch.dict(sys.modules, {
            'openedx': MagicMock(),
            'openedx.features': MagicMock(),
            'openedx.features.enterprise_support': MagicMock(),
            'openedx.features.enterprise_support.api': enterprise_support_api_mod,
            'openedx.features.enterprise_support.utils': enterprise_support_utils_mod,
        }):
            return step.run_filter(context=context, request=request)


class TestLogistrationContextEnricherWithCustomer(unittest.TestCase):
    """
    Tests for LogistrationContextEnricher when an enterprise customer is found.
    """

    def _make_step(self):
        from enterprise.filters.logistration import LogistrationContextEnricher
        return LogistrationContextEnricher('test-filter', {})

    def test_run_filter_with_enterprise_customer_updates_context(self):
        """
        When an enterprise customer is found and context has 'data', slug login URL
        and is_enterprise_enable flag are injected.
        """
        step = self._make_step()
        request = MagicMock()
        enterprise_customer = MagicMock()
        context = {'data': {}}

        mock_ecfr = MagicMock(return_value=enterprise_customer)
        mock_update = MagicMock()
        mock_get_slug = MagicMock(return_value='https://example.com/slug-login/')

        enterprise_support_api_mod = MagicMock()
        enterprise_support_api_mod.enterprise_customer_for_request = mock_ecfr

        enterprise_support_utils_mod = MagicMock()
        enterprise_support_utils_mod.update_logistration_context_for_enterprise = mock_update
        enterprise_support_utils_mod.get_enterprise_slug_login_url = mock_get_slug

        with patch.dict(sys.modules, {
            'openedx': MagicMock(),
            'openedx.features': MagicMock(),
            'openedx.features.enterprise_support': MagicMock(),
            'openedx.features.enterprise_support.api': enterprise_support_api_mod,
            'openedx.features.enterprise_support.utils': enterprise_support_utils_mod,
        }):
            result = step.run_filter(context=context, request=request)

        self.assertEqual(result['request'], request)
        # update_logistration_context_for_enterprise should have been called
        mock_update.assert_called_once_with(request, context, enterprise_customer)
        # slug login URL and enterprise flag should be set
        self.assertEqual(result['context']['data']['enterprise_slug_login_url'], 'https://example.com/slug-login/')
        self.assertTrue(result['context']['data']['is_enterprise_enable'])

    def test_run_filter_with_enterprise_customer_no_data_key(self):
        """
        When enterprise customer is found but context has no 'data' key,
        update is still called but no KeyError occurs.
        """
        step = self._make_step()
        request = MagicMock()
        enterprise_customer = MagicMock()
        context = {}

        mock_ecfr = MagicMock(return_value=enterprise_customer)
        mock_update = MagicMock()
        mock_get_slug = MagicMock(return_value='https://example.com/slug-login/')

        enterprise_support_api_mod = MagicMock()
        enterprise_support_api_mod.enterprise_customer_for_request = mock_ecfr

        enterprise_support_utils_mod = MagicMock()
        enterprise_support_utils_mod.update_logistration_context_for_enterprise = mock_update
        enterprise_support_utils_mod.get_enterprise_slug_login_url = mock_get_slug

        with patch.dict(sys.modules, {
            'openedx': MagicMock(),
            'openedx.features': MagicMock(),
            'openedx.features.enterprise_support': MagicMock(),
            'openedx.features.enterprise_support.api': enterprise_support_api_mod,
            'openedx.features.enterprise_support.utils': enterprise_support_utils_mod,
        }):
            result = step.run_filter(context=context, request=request)

        mock_update.assert_called_once_with(request, context, enterprise_customer)
        # 'data' key was not present, so no slug url or flag should be added
        self.assertNotIn('data', result['context'])


class TestLogistrationCookieSetter(unittest.TestCase):
    """
    Tests for the LogistrationCookieSetter pipeline step.
    """

    def _make_step(self):
        from enterprise.filters.logistration import LogistrationCookieSetter
        return LogistrationCookieSetter('test-filter', {})

    def test_run_filter_returns_unchanged_context(self):
        """
        run_filter returns context and request unchanged (cookie setting is a side-effect).
        """
        step = self._make_step()
        request = MagicMock()
        context = {'data': {'key': 'value'}}

        enterprise_support_utils = MagicMock()
        enterprise_support_utils.handle_enterprise_cookies_for_logistration = MagicMock()

        with patch.dict(sys.modules, {
            'openedx': MagicMock(),
            'openedx.features': MagicMock(),
            'openedx.features.enterprise_support': enterprise_support_utils,
            'openedx.features.enterprise_support.utils': enterprise_support_utils,
        }):
            result = step.run_filter(context=context, request=request)

        self.assertEqual(result['context'], context)
        self.assertEqual(result['request'], request)


class TestPostLoginEnterpriseRedirect(unittest.TestCase):
    """
    Tests for the PostLoginEnterpriseRedirect pipeline step.
    """

    def _make_step(self):
        from enterprise.filters.logistration import PostLoginEnterpriseRedirect
        return PostLoginEnterpriseRedirect('test-filter', {})

    def _run_with_enterprise_data(self, enterprise_data, next_url='/dashboard', original_redirect='/home'):
        step = self._make_step()
        user = MagicMock()

        api_mod = MagicMock()
        api_mod.get_enterprise_learner_data_from_api = MagicMock(return_value=enterprise_data)

        with patch.dict(sys.modules, {
            'openedx': MagicMock(),
            'openedx.features': MagicMock(),
            'openedx.features.enterprise_support': api_mod,
            'openedx.features.enterprise_support.api': api_mod,
        }):
            return step.run_filter(
                redirect_url=original_redirect,
                user=user,
                next_url=next_url,
            )

    def test_run_filter_no_enterprise_data(self):
        """
        When enterprise_data is empty, original redirect_url is returned unchanged.
        """
        result = self._run_with_enterprise_data(enterprise_data=[])
        self.assertEqual(result['redirect_url'], '/home')

    def test_run_filter_single_enterprise(self):
        """
        When user is in exactly one enterprise, original redirect_url is returned unchanged.
        """
        result = self._run_with_enterprise_data(enterprise_data=[MagicMock()])
        self.assertEqual(result['redirect_url'], '/home')

    def test_run_filter_multiple_enterprises_redirects_to_selection(self):
        """
        When user is in multiple enterprises, redirect to enterprise selection page.
        """
        result = self._run_with_enterprise_data(
            enterprise_data=[MagicMock(), MagicMock()],
            next_url='/dashboard',
        )
        self.assertIn('/enterprise/select/active', result['redirect_url'])
        self.assertIn('success_url', result['redirect_url'])
        self.assertIn('/dashboard', result['redirect_url'])

    def test_run_filter_multiple_enterprises_no_next_url(self):
        """
        When user is in multiple enterprises and next_url is None, uses '/' as fallback.
        """
        result = self._run_with_enterprise_data(
            enterprise_data=[MagicMock(), MagicMock()],
            next_url=None,
        )
        self.assertIn('/enterprise/select/active', result['redirect_url'])
        self.assertIn('success_url', result['redirect_url'])
        # next_url falls back to '/', so the URL ends with success_url=/
        self.assertTrue(result['redirect_url'].endswith('success_url=/'))

    def test_run_filter_api_exception_returns_original_redirect(self):
        """
        When get_enterprise_learner_data_from_api raises an exception,
        the original redirect_url is returned without raising.
        """
        step = self._make_step()
        user = MagicMock()

        api_mod = MagicMock()
        api_mod.get_enterprise_learner_data_from_api = MagicMock(
            side_effect=RuntimeError('API unavailable')
        )

        with patch.dict(sys.modules, {
            'openedx': MagicMock(),
            'openedx.features': MagicMock(),
            'openedx.features.enterprise_support': api_mod,
            'openedx.features.enterprise_support.api': api_mod,
        }):
            result = step.run_filter(
                redirect_url='/original',
                user=user,
                next_url='/next',
            )

        self.assertEqual(result['redirect_url'], '/original')
