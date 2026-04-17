"""
Pipeline steps for the student dashboard filter.
"""
import logging

from openedx_filters.filters import PipelineStep

log = logging.getLogger(__name__)

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

    Injects: enterprise_message, consent_required_courses, is_enterprise_user, and
    enterprise learner portal context keys.
    """

    def run_filter(self, context, template_name):  # pylint: disable=arguments-differ
        """
        Inject enterprise data into the dashboard context.
        """
        request = context.get('request')
        user = context.get('user')
        course_enrollments = context.get('course_enrollment_pairs', [])

        if user is None:
            return {'context': context, 'template_name': template_name}

        try:
            enterprise_message = get_dashboard_consent_notification(request, user, course_enrollments)
        except Exception:  # pylint: disable=broad-except
            log.warning('Failed to fetch enterprise dashboard consent notification.', exc_info=True)
            enterprise_message = ''

        try:
            enterprise_learner_portal_context = get_enterprise_learner_portal_context(request)
        except Exception:  # pylint: disable=broad-except
            log.warning('Failed to fetch enterprise learner portal context.', exc_info=True)
            enterprise_learner_portal_context = {}

        context['enterprise_message'] = enterprise_message
        context['is_enterprise_user'] = is_enterprise_learner(user)
        context.update(enterprise_learner_portal_context)

        return {'context': context, 'template_name': template_name}
