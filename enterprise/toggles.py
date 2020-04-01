# -*- coding: utf-8 -*-
"""
Toggles for edx-enterprise.
"""


from __future__ import absolute_import, unicode_literals

try:
    from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers
except ImportError:
    configuration_helpers = None

try:
    from openedx.core.djangoapps.waffle_utils import WaffleFlag, WaffleFlagNamespace
except ImportError:
    WaffleFlag = None
    WaffleFlagNamespace = None


# Namespace for learner profile waffle flags.
WAFFLE_FLAG_NAMESPACE = WaffleFlagNamespace(name='enterprise')

# Waffle flag to redirect to another learner profile experience.
# .. toggle_name: enterprise.enterprise_catalog_api_enabled
# .. toggle_implementation: WaffleFlag
# .. toggle_default: False
# .. toggle_description: Supports percentage rollout for use of enterprise-catalog API endpoints.
# .. toggle_category: ??
# .. toggle_use_cases: incremental_release
# .. toggle_creation_date: tbd
# .. toggle_expiration_date: tbd
# .. toggle_warnings:
# .. toggle_tickets:
# .. toggle_status:
ENTERPRISE_CATALOG_API_ENABLED = WaffleFlag(WAFFLE_FLAG_NAMESPACE, 'enterprise_catalog_api_enabled')


def should_use_enterprise_catalog_api():
    """
    Returns enterprise.enterprise_catalog_api_enabled WaffleFlag value if enabled.
    """
    return (
        configuration_helpers.get_value('ENABLE_ENTERPRISE_CATALOG_API_ENDPOINTS') and
        ENTERPRISE_CATALOG_API_ENABLED.is_enabled()
    )
