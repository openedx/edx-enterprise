"""
Waffle toggles for enterprise features within the LMS.
"""

import crum

from waffle import flag_is_active
from waffle.models import Flag

from edx_toggles.toggles import WaffleFlag
from enterprise.models import EnterpriseCustomerUser, EnterpriseWaffleFlagPercentage

ENTERPRISE_NAMESPACE = 'enterprise'
ENTERPRISE_LOG_PREFIX = 'Enterprise: '


class EnterpriseWaffleFlag(WaffleFlag):
    """
    Waffle flag that can be enabled for a percentage of users
    within a specific enterprise customer.

    If a percentage override is found for the given enterprise, it will be
    used. Otherwise, it falls back to the standard waffle flag behavior.
    """

    def is_enabled(self, enterprise_customer_uuid=None):
        """
        Returns whether the feature flag is enabled for the given request and enterprise customer.
        """
        request = crum.get_current_request()
        user = request.user
        # 1. We must have a request, user, and enterprise context to proceed.
        if not all([request, (user and user.is_authenticated), enterprise_customer_uuid]):
            return False

        # 2. The user must be an active, linked member of the enterprise.
        if not EnterpriseCustomerUser.objects.filter(
            user_id=user.id,
            enterprise_customer__uuid=enterprise_customer_uuid,
            linked=True,
            active=True,
        ).exists():
            return False

        # 3. Get the waffle flag from the database.
        try:
            flag = Flag.objects.get(name=self.name)
        except Flag.DoesNotExist:
            return False

        # 4. Check for an enterprise-specific percentage override.
        flag_override = EnterpriseWaffleFlagPercentage.objects.filter(
            flag=flag, enterprise_customer__uuid=enterprise_customer_uuid
        ).first()

        if flag_override:
            # An override exists. We use its percentage but still honor all
            # other flag settings (e.g., 'staff', 'superuser', 'testing').
            # We do this by temporarily setting the percentage on the flag
            # object in memory and running the standard `is_active` check.
            flag.percent = flag_override.percent
            return flag.is_active(request)
        else:
            # No override found. Fall back to the default global behavior.
            return flag_is_active(request, self.waffle_name)


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

# .. toggle_name: enterprise.enterprise_learner_bff_concurrent_requests
# .. toggle_implementation: EnterpriseWaffleFlag
# .. toggle_default: False
# .. toggle_description: Enables concurrent requests for the enterprise learner BFF.
# .. toggle_use_cases: open_edx
# .. toggle_creation_date: 2025-06-12
ENTERPRISE_LEARNER_BFF_CONCURRENT_REQUESTS = EnterpriseWaffleFlag(
    f'{ENTERPRISE_NAMESPACE}.enterprise_learner_bff_concurrent_requests',
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
    }


def get_features_by_enterprise_customer(flags):
    """
    Returns a mapping of enterprise UUIDs to their flag statuses.
    
    Args:
        flags: A dictionary of flag names to flag instances
              Example: {
                  'enterprise_learner_bff_concurrent_requests': ENTERPRISE_LEARNER_BFF_CONCURRENT_REQUESTS,
              }
    
    Returns:
        dict: {
            '<uuid>': {
                'flag_name1': bool,
                'flag_name2': bool,
                ...
            },
            ...
        }
    """
    request = crum.get_current_request()
    user = getattr(request, 'user', None)

    if not user or not user.is_authenticated:
        return {}

    enterprise_customer_uuids = EnterpriseCustomerUser.objects.filter(
        user_id=user.id,
        linked=True,
        active=True,
        enterprise_customer__active=True,
    ).values_list('enterprise_customer__uuid', flat=True)

    return {
        str(uuid): {
            flag_name: flag.is_enabled(enterprise_customer_uuid=uuid)
            for flag_name, flag in flags.items()
        }
        for uuid in enterprise_customer_uuids
    }


def enterprise_features_by_customer():
    """
    Returns a dict of enterprise Waffle-based feature flags.
    """
    return get_features_by_enterprise_customer({
        'enterprise_learner_bff_concurrent_requests': ENTERPRISE_LEARNER_BFF_CONCURRENT_REQUESTS,
    })
