"""
Pipeline steps for the course enrollment filter.
"""
import logging
from typing import Any

from openedx_filters.filters import PipelineStep

from django.contrib.auth.base_user import AbstractBaseUser

from enterprise.models import EnterpriseCustomerUser

log = logging.getLogger(__name__)


class EnterpriseEnrollmentPostProcessor(PipelineStep):
    """
    Post-enrollment pipeline step: notify enterprise API and record consent.

    When an enterprise customer user enrolls in a course, this step calls the enterprise and consent
    API clients to post the enrollment and provide consent on behalf of the enterprise customer.

    This step is intended to be registered as a pipeline step for the
    ``org.openedx.learning.course.enrollment.started.v1`` filter.
    """

    def run_filter(self, user: AbstractBaseUser, course_key: Any, mode: str) -> dict[str, Any]:  # pylint: disable=arguments-differ
        """
        Post enterprise enrollment and consent if the user is an enterprise customer user.
        """
        try:
            from openedx.features.enterprise_support.api import (  # pylint: disable=import-outside-toplevel
                ConsentApiServiceClient,
                EnterpriseApiServiceClient,
            )
        except ImportError:
            return {'user': user, 'course_key': course_key, 'mode': mode}

        enterprise_customer_user = (
            EnterpriseCustomerUser.objects.select_related('enterprise_customer')
            .filter(user=user)
            .first()
        )
        if enterprise_customer_user is None:
            return {'user': user, 'course_key': course_key, 'mode': mode}

        enterprise_customer_uuid = str(enterprise_customer_user.enterprise_customer.uuid)
        username = user.username
        course_id = str(course_key)

        try:
            EnterpriseApiServiceClient().post_enterprise_course_enrollment(
                username,
                course_id,
                consent_granted=True,
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
                enterprise_customer_uuid=enterprise_customer_uuid,
            )
        except Exception:  # pylint: disable=broad-except
            log.exception(
                "Failed to provide enterprise consent for user %s in course %s.",
                username,
                course_id,
            )

        return {'user': user, 'course_key': course_key, 'mode': mode}
