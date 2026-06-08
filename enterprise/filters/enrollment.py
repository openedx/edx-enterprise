"""
Pipeline steps for the course enrollment filter.
"""
import logging
from typing import Any

from openedx_filters.filters import PipelineStep

from django.contrib.auth.base_user import AbstractBaseUser

log = logging.getLogger(__name__)

try:
    from openedx.features.enterprise_support.api import ConsentApiServiceClient, EnterpriseApiServiceClient
except ImportError:
    ConsentApiServiceClient = None
    EnterpriseApiServiceClient = None


class EnterpriseEnrollmentViewProcessor(PipelineStep):
    """
    Enrollment pipeline step: notify enterprise API and record consent.

    When an enterprise customer user enrolls in a course, this step calls the enterprise and consent
    API clients to post the enrollment and provide consent on behalf of the enterprise customer.

    This step is intended to be registered as a pipeline step for the
    ``org.openedx.learning.course.enrollment.view.started.v1`` filter.
    """

    def run_filter(  # pylint: disable=arguments-differ
            self,
            user: AbstractBaseUser,
            course_key: Any,
            linked_enterprise: str | None,
            has_api_key_permissions: bool
    ) -> dict[str, Any]:
        """
        Post enterprise enrollment and consent if the user is an enterprise customer user.
        """
        log.info(
            "EnterpriseEnrollmentViewProcessor running: user_id=%s, course_key=%s, "
            + "linked_enterprise=%s, api_permissions=%s",
            user.id,
            str(course_key),
            linked_enterprise,
            has_api_key_permissions,
        )
        if linked_enterprise is None or not has_api_key_permissions:
            return {
                'user': user,
                'course_key': course_key,
                'linked_enterprise': linked_enterprise,
                'has_api_key_permissions': has_api_key_permissions
            }

        username = user.username
        course_id = str(course_key)
        try:
            EnterpriseApiServiceClient().post_enterprise_course_enrollment(
                username,
                course_id,
            )
        except Exception:  # pylint: disable=broad-except
            log.exception(
                "Failed to post enterprise course enrollment for user %s in course %s.",
                username,
                course_id,
            )

        try:
            ConsentApiServiceClient().provide_consent(
                username=username,
                course_id=course_id,
                enterprise_customer_uuid=str(linked_enterprise),
            )
        except Exception:  # pylint: disable=broad-except
            log.exception(
                "Failed to provide enterprise consent for user %s in course %s.",
                username,
                course_id,
            )

        return {
            'user': user,
            'course_key': course_key,
            'linked_enterprise': linked_enterprise,
            'has_api_key_permissions': has_api_key_permissions
        }
