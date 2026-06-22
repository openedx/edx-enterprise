"""
Pipeline steps for courseware filters, contributed by the Consent app.

DataSharingConsentRedirectStep and DataSharingConsentCourseAccessStep both enforce the
same consent requirement but are registered against different platform hooks that fire
at different points in the courseware experience. The two hooks may sometimes run in
the same request, but not always — so both registrations are necessary to ensure
consent is enforced across all entry points.
"""
import logging
from typing import Any

from crum import get_current_request
from opaque_keys.edx.keys import CourseKey
from openedx_filters.filters import PipelineStep
from openedx_filters.learning.filters import CoursewareAccessChecksRequested, CoursewareViewStarted

from consent.helpers import get_enterprise_consent_url

log = logging.getLogger(__name__)


class DataSharingConsentRedirectStep(PipelineStep):
    """
    Redirects the user to the consent page when data sharing consent is required.

    Registered against ``org.openedx.learning.courseware.view.started.v1``.
    Raises ``CoursewareViewStarted.RedirectToUrl`` to redirect when consent is needed.
    If consent is not required, the step is a no-op.
    """

    def run_filter(self, course_key: CourseKey, view_name: str) -> dict:  # pylint: disable=arguments-differ
        request = get_current_request()
        log.info(
            "DataSharingConsentRedirectStep running: course_key=%s, view_name=%s, user_id=%s",
            course_key,
            view_name,
            request.user.id if request else None,
        )
        if request is None:
            return {"course_key": course_key, "view_name": view_name}
        consent_url = get_enterprise_consent_url(
            request=request,
            course_id=str(course_key),
            # An enrollment is assumed to exist if a courseware view has started, so just hard-code the value here.
            enrollment_exists=True,
            # `source` is tracked in consent DB records so we can audit which view initiated the consent redirect.
            source=view_name,
            # Omitted kwargs:
            # - user: Defaults to request.user, which matches original decorator behavior.
            # - return_to: Defaults to request.path, which should already be the courseware view.
        )
        # Redirect to the consent page if consent is required.
        if consent_url:
            raise CoursewareViewStarted.RedirectToUrl(
                message="Data sharing consent required",
                redirect_to=consent_url,
            )
        # No consent required — pass through.
        return {"course_key": course_key, "view_name": view_name}


class DataSharingConsentCourseAccessStep(PipelineStep):
    """
    Deny courseware access when data sharing consent is required but not granted.

    Registered against ``org.openedx.learning.courseware.access_checks.requested.v1``.
    Raises ``CoursewareAccessChecksRequested.PreventCoursewareAccess`` to deny
    access when ``get_enterprise_consent_url`` returns a URL.
    """

    def run_filter(self, user: Any, course_key: CourseKey) -> dict:  # pylint: disable=arguments-differ
        log.info(
            "DataSharingConsentCourseAccessStep running: user_id=%s, course_key=%s",
            user.id,
            course_key,
        )
        request = get_current_request()
        if request is None:
            return {"user": user, "course_key": course_key}
        consent_url = get_enterprise_consent_url(
            request=request,
            course_id=str(course_key),
            # We must pass the given user even though the request already has a user attached. They could differ.
            user=user,
            # This is always True since the step only runs in course access checks that require an existing enrollment.
            enrollment_exists=True,
            # After granting consent, make sure to redirect to the courseware view regardless of where they came from.
            return_to="courseware",
            # Identify as originating from the access check context.
            source="CoursewareAccess",
        )
        # Deny courseware access if consent is required.
        if consent_url:
            raise CoursewareAccessChecksRequested.PreventCoursewareAccess(
                message="Data sharing consent required",
                error_code="data_sharing_access_required",
                # developer_message carries the consent redirect URL by convention: the Learning MFE treats this message
                # as a URL when error_code is "data_sharing_access_required" and performs a client-side redirect.
                # See frontend-app-learning/src/shared/access.js.
                developer_message=consent_url,
                user_message="You must give Data Sharing Consent for the course",
            )
        # No consent required — pass through.
        return {"user": user, "course_key": course_key}
