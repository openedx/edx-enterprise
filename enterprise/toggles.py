"""
Waffle toggles for enterprise features within the LMS.
"""

from edx_toggles.toggles import WaffleFlag

ENTERPRISE_NAMESPACE = 'enterprise'
ENTERPRISE_LOG_PREFIX = 'Enterprise: '

# .. toggle_name: enterprise.TOP_DOWN_ASSIGNMENT_REAL_TIME_LCM
# .. toggle_implementation: WaffleFlag
# .. toggle_default: False
# .. toggle_description: Enables top-down assignment
# .. toggle_use_cases: open_edx
# .. toggle_creation_date: 2023-09-15
TOP_DOWN_ASSIGNMENT_REAL_TIME_LCM = WaffleFlag(
    f'{ENTERPRISE_NAMESPACE}.top_down_assignment_real_time_lcm',
    __name__,
    ENTERPRISE_LOG_PREFIX,
)

# .. toggle_name: enterprise.feature_prequery_search_suggestions
# .. toggle_implementation: WaffleFlag
# .. toggle_default: False
# .. toggle_description: Enables prequery search suggestions
# .. toggle_use_cases: open_edx
# .. toggle_creation_date: 2024-01-31
FEATURE_PREQUERY_SEARCH_SUGGESTIONS = WaffleFlag(
    f'{ENTERPRISE_NAMESPACE}.feature_prequery_search_suggestions',
    __name__,
    ENTERPRISE_LOG_PREFIX,
)


# .. toggle_name: enterprise.enterprise_customer_support_tool
# .. toggle_implementation: WaffleFlag
# .. toggle_default: False
# .. toggle_description: Enables the enterprise customer support tool
# .. toggle_use_cases: open_edx
# .. toggle_creation_date: 2024-07-17
ENTERPRISE_CUSTOMER_SUPPORT_TOOL = WaffleFlag(
    f'{ENTERPRISE_NAMESPACE}.enterprise_customer_support_tool',
    __name__,
    ENTERPRISE_LOG_PREFIX,
)

# .. toggle_name: enterprise.enterprise_learner_bff_enabled
# .. toggle_implementation: WaffleFlag
# .. toggle_default: False
# .. toggle_description: Enables the enterprise learner BFF
# .. toggle_use_cases: open_edx
# .. toggle_creation_date: 2024-12-16
ENTERPRISE_LEARNER_BFF_ENABLED = WaffleFlag(
    f'{ENTERPRISE_NAMESPACE}.learner_bff_enabled',
    __name__,
    ENTERPRISE_LOG_PREFIX,
)

# .. toggle_name: enterprise.admin_portal_learner_profile_view_enabled
# .. toggle_implementation: WaffleFlag
# .. toggle_default: False
# .. toggle_description: Enables an admin to view a learner's profile
# .. toggle_use_cases: open_edx
# .. toggle_creation_date: 2025-02-12
ADMIN_PORTAL_LEARNER_PROFILE_VIEW_ENABLED = WaffleFlag(
    f'{ENTERPRISE_NAMESPACE}.admin_portal_learner_profile_view_enabled',
    __name__,
    ENTERPRISE_LOG_PREFIX,
)

# .. toggle_name: enterprise.catalog_query_search_filters_enabled
# .. toggle_implementation: WaffleFlag
# .. toggle_default: False
# .. toggle_description: Enables filtering search results by catalog queries vs. enterprise-specific attributes.
# .. toggle_use_cases: open_edx
# .. toggle_creation_date: 2025-03-02
CATALOG_QUERY_SEARCH_FILTERS_ENABLED = WaffleFlag(
    f'{ENTERPRISE_NAMESPACE}.catalog_query_search_filters_enabled',
    __name__,
    ENTERPRISE_LOG_PREFIX,
)

# .. toggle_name: enterprise.enterprise_admin_onboarding
# .. toggle_implementation: WaffleFlag
# .. toggle_default: False
# .. toggle_description: Enables the admin onboarding tour on the admin-portal.
# .. toggle_use_cases: open_edx
# .. toggle_creation_date: 2025-05-12
ENTERPRISE_ADMIN_ONBOARDING = WaffleFlag(
    f'{ENTERPRISE_NAMESPACE}.enterprise_admin_onboarding',
    __name__,
    ENTERPRISE_LOG_PREFIX,
)

# .. toggle_name: enterprise.edit_highlights_enabled
# .. toggle_implementation: WaffleFlag
# .. toggle_default: False
# .. toggle_description: Enables the Edit Highlights experience.
# .. toggle_use_cases: open_edx
# .. toggle_creation_date: 2025-07-21
EDIT_HIGHLIGHTS_ENABLED = WaffleFlag(
    f'{ENTERPRISE_NAMESPACE}.edit_highlights_enabled',
    __name__,
    ENTERPRISE_LOG_PREFIX,
)


def top_down_assignment_real_time_lcm():
    """
    Returns whether top-down assignment and real time LCM feature flag is enabled.
    """
    return TOP_DOWN_ASSIGNMENT_REAL_TIME_LCM.is_enabled()


def feature_prequery_search_suggestions():
    """
    Returns whether the prequery search suggestion feature flag is enabled.
    """
    return FEATURE_PREQUERY_SEARCH_SUGGESTIONS.is_enabled()


def enterprise_customer_support_tool():
    """
    Returns whether the enterprise customer support tool is enabled.
    """
    return ENTERPRISE_CUSTOMER_SUPPORT_TOOL.is_enabled()


def enterprise_learner_bff_enabled():
    """
    Returns whether the enterprise learner BFF is enabled.
    """
    return ENTERPRISE_LEARNER_BFF_ENABLED.is_enabled()


def admin_portal_learner_profile_view_enabled():
    """
    Returns whether the learner profile view in admin portal is enabled.
    """
    return ADMIN_PORTAL_LEARNER_PROFILE_VIEW_ENABLED.is_enabled()


def catalog_query_search_filters_enabled():
    """
    Returns whether the catalog query search filters feature flag is enabled.
    """
    return CATALOG_QUERY_SEARCH_FILTERS_ENABLED.is_enabled()


def enterprise_admin_onboarding_enabled():
    """
    Returns whether the admin onboarding feature flag is enabled.
    """
    return ENTERPRISE_ADMIN_ONBOARDING.is_enabled()


def enterprise_edit_highlights_enabled():
    """
    Returns whether the edit highlights feature flag is enabled.
    """
    return EDIT_HIGHLIGHTS_ENABLED.is_enabled()


def enterprise_features():
    """
    Returns a dict of enterprise Waffle-based feature flags.
    """
    return {
        'top_down_assignment_real_time_lcm': top_down_assignment_real_time_lcm(),
        'feature_prequery_search_suggestions': feature_prequery_search_suggestions(),
        'enterprise_customer_support_tool': enterprise_customer_support_tool(),
        'enterprise_learner_bff_enabled': enterprise_learner_bff_enabled(),
        'admin_portal_learner_profile_view_enabled': admin_portal_learner_profile_view_enabled(),
        'catalog_query_search_filters_enabled': catalog_query_search_filters_enabled(),
        'enterprise_admin_onboarding_enabled': enterprise_admin_onboarding_enabled(),
        'enterprise_edit_highlights_enabled': enterprise_edit_highlights_enabled(),
    }
