"""
Pipeline steps for the student dashboard filter.
"""
import logging
from typing import Any

from crum import get_current_request
from openedx_filters.filters import PipelineStep

# ENT-11576: These functions will be migrated from the platform's enterprise_support module
# into edx-enterprise, eliminating these cross-boundary imports.
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

log = logging.getLogger(__name__)


class DashboardContextEnricher(PipelineStep):
    """
    Enrich the student dashboard context with enterprise-specific data.

    Injects: enterprise_message, is_enterprise_user, and enterprise learner portal context keys.
    """

    def run_filter(self, context: dict[str, Any], template_name: str) -> dict[str, Any]:  # pylint: disable=arguments-differ
        """
        Inject enterprise data into the dashboard context.
        """
        log.info(
            "DashboardContextEnricher running: template_name=%s, context_keys=%s, user_id=%s",
            template_name,
            sorted(context.keys()),
            getattr(context.get("user"), "id", None),
        )
        user = context.get('user')
        course_enrollments = context.get('course_enrollments', [])

        if user is None:
            return {'context': context, 'template_name': template_name}

        request = get_current_request()

        enterprise_message = get_dashboard_consent_notification(request, user, course_enrollments)

        enterprise_learner_portal_context = get_enterprise_learner_portal_context(request)

        context['enterprise_message'] = enterprise_message
        context['is_enterprise_user'] = is_enterprise_learner(user)
        context.update(enterprise_learner_portal_context)

        return {'context': context, 'template_name': template_name}
