"""
Pipeline steps for courseware view redirect URL determination.
"""
from openedx_filters.filters import PipelineStep

# These imports will be replaced with internal paths in epic 17 when
# enterprise_support is migrated into edx-enterprise.
try:
    from openedx.features.enterprise_support.api import get_enterprise_consent_url
except ImportError:
    get_enterprise_consent_url = None

try:
    from openedx.features.enterprise_support.api import (
        enterprise_customer_from_session_or_learner_data,
    )
except ImportError:
    enterprise_customer_from_session_or_learner_data = None

from enterprise.models import EnterpriseCustomerUser


class ConsentRedirectStep(PipelineStep):
    """
    Appends a data-sharing consent redirect URL when the user has not yet consented.

    This step is intended to be registered as a pipeline step for the
    ``org.openedx.learning.courseware.view.redirect_url.requested.v1`` filter.

    If the user is required to grant data-sharing consent before accessing the course,
    the consent URL is appended to ``redirect_urls``.
    """

    def run_filter(self, redirect_urls, request, course_key):  # pylint: disable=arguments-differ
        """
        Append consent redirect URL when data-sharing consent is required.

        Arguments:
            redirect_urls (list): current list of redirect URLs.
            request (HttpRequest): the current Django HTTP request.
            course_key (CourseKey): the course key for the view being accessed.

        Returns:
            dict: updated pipeline data with ``redirect_urls`` possibly extended.
        """
        consent_url = get_enterprise_consent_url(request, str(course_key))
        if consent_url:
            redirect_urls = list(redirect_urls) + [consent_url]
        return {"redirect_urls": redirect_urls, "request": request, "course_key": course_key}


class LearnerPortalRedirectStep(PipelineStep):
    """
    Appends a learner portal redirect URL when the learner is enrolled via an enterprise portal.

    This step is intended to be registered as a pipeline step for the
    ``org.openedx.learning.courseware.view.redirect_url.requested.v1`` filter.

    If the learner's current enterprise requires courseware access through the learner portal,
    the portal redirect URL is appended to ``redirect_urls``.
    """

    def run_filter(self, redirect_urls, request, course_key):  # pylint: disable=arguments-differ
        """
        Append learner portal redirect URL when the learner is enrolled via enterprise portal.

        Arguments:
            redirect_urls (list): current list of redirect URLs.
            request (HttpRequest): the current Django HTTP request.
            course_key (CourseKey): the course key for the view being accessed.

        Returns:
            dict: updated pipeline data with ``redirect_urls`` possibly extended.
        """
        enterprise_customer = enterprise_customer_from_session_or_learner_data(request)
        if enterprise_customer:
            user = request.user
            is_enrolled_via_portal = EnterpriseCustomerUser.objects.filter(
                user_id=user.id,
                enterprise_customer__uuid=enterprise_customer.get('uuid'),
            ).exists()
            if is_enrolled_via_portal:
                portal_url = enterprise_customer.get('learner_portal_url')
                if portal_url:
                    redirect_urls = list(redirect_urls) + [portal_url]
        return {"redirect_urls": redirect_urls, "request": request, "course_key": course_key}
