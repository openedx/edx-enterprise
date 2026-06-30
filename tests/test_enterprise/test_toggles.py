"""
Tests for enterprise/toggles.py.
"""
import ddt
from edx_toggles.toggles.testutils import override_waffle_flag

from django.test import TestCase

from enterprise.toggles import USE_ALGOLIA_INDEX_V2, enterprise_features


@ddt.ddt
class TestEnterpriseFeatures(TestCase):
    """Tests for enterprise_features()."""

    @ddt.data(True, False)
    def test_use_algolia_index_v2(self, active):
        with override_waffle_flag(USE_ALGOLIA_INDEX_V2, active=active):
            assert enterprise_features()['use_algolia_index_v2'] is active
