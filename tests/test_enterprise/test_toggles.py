"""
Tests for enterprise/toggles.py.
"""
import ddt
from edx_toggles.toggles.testutils import override_waffle_flag

from django.test import TestCase

from enterprise.toggles import PERSONALIZED_SEARCH_ENABLED, USE_ALGOLIA_INDEX_V2, enterprise_features


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
