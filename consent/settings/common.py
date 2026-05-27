"""
Common plugin settings for the consent app.
"""
# The consent and enterprise plugins are shipped together and never installed
# independently, so it's fine for consent to reuse the merge helper from the
# enterprise plugin's settings module.
from enterprise.settings.common import FiltersConfig, _merge_filters_config

CONSENT_FILTERS_CONFIG: FiltersConfig = {}


def plugin_settings(settings):
    """
    Override platform settings for the consent app.

    This is called by the Open edX plugin system during LMS/CMS startup. Add
    any Django settings overrides here (e.g. ``settings.SOME_FLAG = True``).

    Args:
        settings: The Django settings module being configured.
    """
    # Skip injecting any default consent settings if the enterprise feature is entirely disabled.
    if not getattr(settings, 'ENABLE_ENTERPRISE_INTEGRATION', False):
        return

    # Merge consent filter pipeline steps into OPEN_EDX_FILTERS_CONFIG so we never clobber
    # operator-defined entries (e.g. extra pipeline steps configured via YAML).
    filters_config = getattr(settings, 'OPEN_EDX_FILTERS_CONFIG', None)
    if filters_config is None:
        filters_config = {}
        settings.OPEN_EDX_FILTERS_CONFIG = filters_config
    _merge_filters_config(filters_config, CONSENT_FILTERS_CONFIG)
