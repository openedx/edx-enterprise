"""
Tests for enterprise plugin settings (enterprise/settings/common.py).
"""
import unittest
from types import SimpleNamespace

import ddt
import pytest

from enterprise.settings.common import ENTERPRISE_FILTERS_CONFIG, _merge_filters_config, plugin_settings


class TestPluginSettingsPipelineInjection(unittest.TestCase):
    """
    Tests for SOCIAL_AUTH_PIPELINE step injection in plugin_settings().
    """

    def _make_settings(self, pipeline=None, enable_enterprise_integration=True):
        """Return a simple settings namespace with the given pipeline."""
        return SimpleNamespace(
            SOCIAL_AUTH_PIPELINE=pipeline,
            ENABLE_ENTERPRISE_INTEGRATION=enable_enterprise_integration,
        )

    def _base_pipeline(self):
        """Return a minimal pipeline list resembling the platform default."""
        return [
            'common.djangoapps.third_party_auth.pipeline.parse_query_params',
            'social_core.pipeline.social_auth.social_details',
            'social_core.pipeline.social_auth.social_uid',
            'social_core.pipeline.social_auth.auth_allowed',
            'social_core.pipeline.social_auth.social_user',
            'common.djangoapps.third_party_auth.pipeline.associate_by_email_if_login_api',
            'common.djangoapps.third_party_auth.pipeline.associate_by_email_if_oauth',
            'common.djangoapps.third_party_auth.pipeline.get_username',
            'common.djangoapps.third_party_auth.pipeline.set_pipeline_timeout',
            'common.djangoapps.third_party_auth.pipeline.ensure_user_information',
            'social_core.pipeline.user.create_user',
            'social_core.pipeline.social_auth.associate_user',
            'social_core.pipeline.social_auth.load_extra_data',
            'social_core.pipeline.user.user_details',
            'common.djangoapps.third_party_auth.pipeline.user_details_force_sync',
            'common.djangoapps.third_party_auth.pipeline.set_id_verification_status',
            'common.djangoapps.third_party_auth.pipeline.set_logged_in_cookies',
            'common.djangoapps.third_party_auth.pipeline.login_analytics',
            'common.djangoapps.third_party_auth.pipeline.ensure_redirect_url_is_safe',
        ]

    def test_inserts_email_step_before_oauth(self):
        """
        enterprise_associate_by_email should be inserted immediately before
        associate_by_email_if_oauth.
        """
        pipeline = self._base_pipeline()
        settings = self._make_settings(pipeline=pipeline)
        plugin_settings(settings)

        email_step = 'enterprise.tpa_pipeline.enterprise_associate_by_email'
        oauth_step = 'common.djangoapps.third_party_auth.pipeline.associate_by_email_if_oauth'
        assert email_step in pipeline
        assert pipeline.index(email_step) == pipeline.index(oauth_step) - 1

    def test_inserts_logistration_step_after_associate_user(self):
        """
        handle_enterprise_logistration should be inserted immediately after
        associate_user.
        """
        pipeline = self._base_pipeline()
        settings = self._make_settings(pipeline=pipeline)
        plugin_settings(settings)

        logistration_step = 'enterprise.tpa_pipeline.handle_enterprise_logistration'
        associate_step = 'social_core.pipeline.social_auth.associate_user'
        assert logistration_step in pipeline
        assert pipeline.index(logistration_step) == pipeline.index(associate_step) + 1

    def test_idempotent(self):
        """
        Calling plugin_settings() twice should not duplicate pipeline entries.
        """
        pipeline = self._base_pipeline()
        settings = self._make_settings(pipeline=pipeline)
        plugin_settings(settings)
        plugin_settings(settings)

        email_step = 'enterprise.tpa_pipeline.enterprise_associate_by_email'
        logistration_step = 'enterprise.tpa_pipeline.handle_enterprise_logistration'
        assert pipeline.count(email_step) == 1
        assert pipeline.count(logistration_step) == 1

    def test_raises_when_oauth_reference_step_missing(self):
        """
        If the reference step (associate_by_email_if_oauth) is missing from
        the pipeline, plugin_settings should raise ValueError.
        """
        pipeline = [
            'social_core.pipeline.social_auth.social_user',
            'social_core.pipeline.social_auth.associate_user',
        ]
        settings = self._make_settings(pipeline=pipeline)
        with pytest.raises(ValueError):
            plugin_settings(settings)

    def test_raises_when_associate_user_reference_step_missing(self):
        """
        If the reference step (associate_user) is missing from the pipeline,
        plugin_settings should raise ValueError.
        """
        pipeline = [
            'common.djangoapps.third_party_auth.pipeline.associate_by_email_if_oauth',
        ]
        settings = self._make_settings(pipeline=pipeline)
        with pytest.raises(ValueError):
            plugin_settings(settings)

    def test_no_pipeline_attribute(self):
        """
        If settings has no SOCIAL_AUTH_PIPELINE, plugin_settings is a no-op
        (even with enterprise integration enabled).
        """
        settings = SimpleNamespace(ENABLE_ENTERPRISE_INTEGRATION=True)
        # Should not raise
        plugin_settings(settings)

    def test_pipeline_is_none(self):
        """
        If SOCIAL_AUTH_PIPELINE is None, plugin_settings is a no-op.
        """
        settings = self._make_settings(pipeline=None)
        # Should not raise
        plugin_settings(settings)

    def test_no_op_when_enterprise_integration_disabled(self):
        """
        If ENABLE_ENTERPRISE_INTEGRATION is False, plugin_settings makes no
        changes to SOCIAL_AUTH_PIPELINE.
        """
        pipeline = self._base_pipeline()
        settings = self._make_settings(pipeline=pipeline, enable_enterprise_integration=False)
        plugin_settings(settings)

        assert 'enterprise.tpa_pipeline.enterprise_associate_by_email' not in pipeline
        assert 'enterprise.tpa_pipeline.handle_enterprise_logistration' not in pipeline


FILTER_A = 'org.openedx.test.filter_a.v1'
FILTER_B = 'org.openedx.test.filter_b.v1'
STEP_X = 'pkg.steps.StepX'
STEP_Y = 'pkg.steps.StepY'
STEP_Z = 'pkg.steps.StepZ'


@ddt.ddt
class TestMergeFiltersConfig(unittest.TestCase):
    """
    Unit tests for the ``_merge_filters_config`` helper. These tests use fabricated
    inputs so they do not need to be updated when ``ENTERPRISE_FILTERS_CONFIG`` grows.
    """

    @ddt.data(
        # Empty existing → additions copied in verbatim.
        {
            'existing': {},
            'additions': {FILTER_A: {'fail_silently': True, 'pipeline': [STEP_X]}},
            'expected': {FILTER_A: {'fail_silently': True, 'pipeline': [STEP_X]}},
        },
        # Existing has an unrelated filter type → preserved alongside the addition.
        {
            'existing': {FILTER_A: {'fail_silently': False, 'pipeline': [STEP_X]}},
            'additions': {FILTER_B: {'fail_silently': True, 'pipeline': [STEP_Y]}},
            'expected': {
                FILTER_A: {'fail_silently': False, 'pipeline': [STEP_X]},
                FILTER_B: {'fail_silently': True, 'pipeline': [STEP_Y]},
            },
        },
        # Existing entry for the same filter type → new step appended; existing fail_silently preserved.
        {
            'existing': {FILTER_A: {'fail_silently': False, 'pipeline': [STEP_X]}},
            'additions': {FILTER_A: {'fail_silently': True, 'pipeline': [STEP_Y]}},
            'expected': {FILTER_A: {'fail_silently': False, 'pipeline': [STEP_X, STEP_Y]}},
        },
        # Partial overlap → duplicate step skipped, novel step appended, order preserved.
        {
            'existing': {FILTER_A: {'fail_silently': False, 'pipeline': [STEP_X, STEP_Y]}},
            'additions': {FILTER_A: {'fail_silently': True, 'pipeline': [STEP_Y, STEP_Z]}},
            'expected': {FILTER_A: {'fail_silently': False, 'pipeline': [STEP_X, STEP_Y, STEP_Z]}},
        },
    )
    @ddt.unpack
    def test_merge_scenarios(self, existing, additions, expected):
        _merge_filters_config(existing, additions)
        assert existing == expected

    def test_idempotent_does_not_duplicate_step(self):
        existing = {}
        additions = {FILTER_A: {'fail_silently': True, 'pipeline': [STEP_X]}}

        _merge_filters_config(existing, additions)
        _merge_filters_config(existing, additions)

        assert existing[FILTER_A]['pipeline'] == [STEP_X]

    def test_additions_dict_isolated_from_subsequent_mutation(self):
        """
        Mutating ``existing`` after a merge must not leak back into the
        ``additions`` dict (i.e., pipeline lists are copied).
        """
        additions = {FILTER_A: {'fail_silently': True, 'pipeline': [STEP_X]}}
        existing = {}

        _merge_filters_config(existing, additions)
        existing[FILTER_A]['pipeline'].append(STEP_Y)

        assert additions[FILTER_A]['pipeline'] == [STEP_X]


class TestEnterpriseFiltersConfig(unittest.TestCase):
    """
    Smoke tests asserting that ``ENTERPRISE_FILTERS_CONFIG`` contains the expected
    filter registrations.  These tests catch omissions when a new pipeline step is
    added to ``enterprise/filters/`` but its filter-type key is never registered.
    """

    def test_all_filters_have_expected_shape(self):
        """
        Every enterprise filter registration should define ``fail_silently`` and
        at least one pipeline step.
        """
        assert ENTERPRISE_FILTERS_CONFIG
        for filter_key, filter_config in ENTERPRISE_FILTERS_CONFIG.items():
            assert "fail_silently" in filter_config, (
                f"Expected {filter_key!r} to define fail_silently"
            )
            assert isinstance(filter_config["pipeline"], list), (
                f"Expected {filter_key!r} pipeline to be a list"
            )
            assert filter_config["pipeline"], (
                f"Expected {filter_key!r} to define at least one pipeline step"
            )

    def test_plugin_settings_injects_all_enterprise_filters(self):
        """
        plugin_settings() should inject every filter key and pipeline step from
        ENTERPRISE_FILTERS_CONFIG into OPEN_EDX_FILTERS_CONFIG.
        """
        settings = SimpleNamespace(
            ENABLE_ENTERPRISE_INTEGRATION=True,
            OPEN_EDX_FILTERS_CONFIG={},
        )
        plugin_settings(settings)

        for filter_key, expected_filter_config in ENTERPRISE_FILTERS_CONFIG.items():
            assert filter_key in settings.OPEN_EDX_FILTERS_CONFIG
            actual_filter_config = settings.OPEN_EDX_FILTERS_CONFIG[filter_key]
            assert actual_filter_config.get("fail_silently") == expected_filter_config.get("fail_silently")
            for expected_step in expected_filter_config.get("pipeline", []):
                assert expected_step in actual_filter_config.get("pipeline", [])
