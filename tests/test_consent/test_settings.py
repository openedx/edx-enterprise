"""
Tests for consent plugin settings (consent/settings/common.py).

The merge helper itself is exercised in ``tests/test_settings.py``; the consent
plugin reuses it via side-import, so we only need a smoke test here.
"""
import unittest
from types import SimpleNamespace

from consent.settings.common import plugin_settings


class TestConsentPluginSettings(unittest.TestCase):
    """
    Smoke tests for consent's plugin_settings() that do not depend on the
    contents of CONSENT_FILTERS_CONFIG.
    """

    def test_no_op_when_enterprise_integration_disabled(self):
        """
        If ENABLE_ENTERPRISE_INTEGRATION is False, plugin_settings makes no
        changes to OPEN_EDX_FILTERS_CONFIG.
        """
        settings = SimpleNamespace(ENABLE_ENTERPRISE_INTEGRATION=False)
        plugin_settings(settings)

        assert not hasattr(settings, 'OPEN_EDX_FILTERS_CONFIG')
