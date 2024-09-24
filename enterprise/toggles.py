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

# .. toggle_name: enterprise.enterprise_groups_v1
# .. toggle_implementation: WaffleFlag
# .. toggle_default: False
# .. toggle_description: Enables enterprise groups feature
# .. toggle_use_cases: open_edx
# .. toggle_creation_date: 2024-02-29
ENTERPRISE_GROUPS_V1 = WaffleFlag(
    f'{ENTERPRISE_NAMESPACE}.enterprise_groups_v1',
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

# .. toggle_name: enterprise.enterprise_groups_v2
# .. toggle_implementation: WaffleFlag
# .. toggle_default: False
# .. toggle_description: Enables enterprise groups feature
# .. toggle_use_cases: open_edx
# .. toggle_creation_date: 2024-09-24
ENTERPRISE_GROUPS_V2 = WaffleFlag(
    f'{ENTERPRISE_NAMESPACE}.enterprise_groups_v2',
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


def enterprise_groups_v1():
    """
    Returns whether the enterprise groups feature flag is enabled.
    """
    return ENTERPRISE_GROUPS_V1.is_enabled()


def enterprise_customer_support_tool():
    """
    Returns whether the enterprise customer support tool is enabled.
    """
    return ENTERPRISE_CUSTOMER_SUPPORT_TOOL.is_enabled()


def enterprise_groups_v2():
    """
    Returns whether the enterprise groups v2 feature flag is enabled.
    """
    return ENTERPRISE_GROUPS_V2.is_enabled()


def enterprise_features():
    """
    Returns a dict of enterprise Waffle-based feature flags.
    """
    return {
        'top_down_assignment_real_time_lcm': top_down_assignment_real_time_lcm(),
        'feature_prequery_search_suggestions': feature_prequery_search_suggestions(),
        'enterprise_groups_v1': enterprise_groups_v1(),
        'enterprise_customer_support_tool': enterprise_customer_support_tool(),
        'enterprise_groups_v2': enterprise_groups_v2(),
    }
