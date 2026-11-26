"""
Tests for enterprise/toggles.py.
"""
import ddt
from edx_toggles.toggles.testutils import override_waffle_flag

from django.test import TestCase

from enterprise.toggles import (
    MULTI_PLAN_FUNDING_ENABLED,
    PERSONALIZED_SEARCH_ENABLED,
    USE_ALGOLIA_INDEX_V2,
    enterprise_features,
)


@ddt.ddt
class TestEnterpriseFeatures(TestCase):
    """Tests for enterprise_features()."""

    @ddt.data(True, False)
    def test_use_algolia_index_v2(self, active):
        with override_waffle_flag(USE_ALGOLIA_INDEX_V2, active=active):
            assert enterprise_features()['use_algolia_index_v2'] is active

    @ddt.data(True, False)
    def test_personalized_search_enabled(self, active):
        with override_waffle_flag(PERSONALIZED_SEARCH_ENABLED, active=active):
            assert enterprise_features()['enterprise_personalized_search_enabled'] is active

    @ddt.data(True, False)
    def test_multi_plan_funding_enabled(self, active):
        with override_waffle_flag(MULTI_PLAN_FUNDING_ENABLED, active=active):
            assert enterprise_features()['enterprise_multi_plan_funding_enabled'] is active

    def test_multi_plan_funding_disabled_by_default(self):
        """With no waffle flag record (as in a fresh environment), the admin portal UI stays off."""
        assert enterprise_features()['enterprise_multi_plan_funding_enabled'] is False
