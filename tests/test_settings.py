"""
Tests for enterprise plugin settings (enterprise/settings/common.py).
"""
import unittest
from types import SimpleNamespace

import pytest

from enterprise.settings.common import plugin_settings


class TestPluginSettingsPipelineInjection(unittest.TestCase):
    """
    Tests for SOCIAL_AUTH_PIPELINE step injection in plugin_settings().
    """

    def _make_settings(self, pipeline=None):
        """Return a simple settings namespace with the given pipeline."""
        return SimpleNamespace(SOCIAL_AUTH_PIPELINE=pipeline)

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
        If settings has no SOCIAL_AUTH_PIPELINE, plugin_settings is a no-op.
        """
        settings = SimpleNamespace()
        # Should not raise
        plugin_settings(settings)

    def test_pipeline_is_none(self):
        """
        If SOCIAL_AUTH_PIPELINE is None, plugin_settings is a no-op.
        """
        settings = self._make_settings(pipeline=None)
        # Should not raise
        plugin_settings(settings)
