"""
Common plugin settings for the enterprise app.
"""


def plugin_settings(settings):  # pylint: disable=unused-argument
    """
    Override platform settings for the enterprise app.

    This is called by the Open edX plugin system during LMS/CMS startup. Add
    any Django settings overrides here (e.g. ``settings.FEATURES['...'] = True``).

    Args:
        settings: The Django settings module being configured.
    """
