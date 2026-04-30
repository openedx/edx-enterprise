"""
Pipeline steps for the student dashboard filter.
"""
from typing import Any

from openedx_filters.filters import PipelineStep

# These imports will be replaced with internal paths in epic 17 when enterprise_support is
# migrated into edx-enterprise.
try:
    from openedx.features.enterprise_support.api import (
        get_dashboard_consent_notification,
        get_enterprise_learner_portal_context,
    )
    from openedx.features.enterprise_support.utils import is_enterprise_learner
except ImportError:
    get_dashboard_consent_notification = None
    get_enterprise_learner_portal_context = None
    is_enterprise_learner = None


class DashboardContextEnricher(PipelineStep):
    """
    Enrich the student dashboard context with enterprise-specific data.

    Injects: enterprise_message, is_enterprise_user, and enterprise learner portal context keys.
    """

    def run_filter(self, context: dict[str, Any], template_name: str) -> dict[str, Any]:  # pylint: disable=arguments-differ
        """
        Inject enterprise data into the dashboard context.
        """
        request = context.get('request')
        user = context.get('user')
        course_enrollments = context.get('course_enrollments', [])

        if user is None:
            return {'context': context, 'template_name': template_name}

        enterprise_message = get_dashboard_consent_notification(request, user, course_enrollments)

        enterprise_learner_portal_context = get_enterprise_learner_portal_context(request)

        context['enterprise_message'] = enterprise_message
        context['is_enterprise_user'] = is_enterprise_learner(user)
        context.update(enterprise_learner_portal_context)

        return {'context': context, 'template_name': template_name}
