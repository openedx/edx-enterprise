"""
Common plugin settings for the enterprise app.
"""


def plugin_settings(settings):
    """
    Override platform settings for the enterprise app.

    This is called by the Open edX plugin system during LMS/CMS startup. Add
    any Django settings overrides here (e.g. ``settings.FEATURES['...'] = True``).

    Args:
        settings: The Django settings module being configured.
    """
    pipeline = getattr(settings, 'SOCIAL_AUTH_PIPELINE', None)
    if pipeline is not None:
        email_step = 'enterprise.tpa_pipeline.enterprise_associate_by_email'
        oauth_step = 'common.djangoapps.third_party_auth.pipeline.associate_by_email_if_oauth'
        if email_step not in pipeline:
            # pipeline.index() intentionally raises ValueError if the reference step is
            # missing — this prevents Django from starting with a misconfigured pipeline.
            pipeline.insert(pipeline.index(oauth_step), email_step)

        logistration_step = 'enterprise.tpa_pipeline.handle_enterprise_logistration'
        associate_step = 'social_core.pipeline.social_auth.associate_user'
        if logistration_step not in pipeline:
            # pipeline.index() intentionally raises ValueError if the reference step is
            # missing — this prevents Django from starting with a misconfigured pipeline.
            pipeline.insert(pipeline.index(associate_step) + 1, logistration_step)
