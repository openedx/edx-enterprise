"""
Pipeline steps for courseware-related openedx-filters contributed by the Enterprise app.
"""
import logging
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from crum import get_current_request
from opaque_keys.edx.keys import CourseKey
from openedx_filters.filters import PipelineStep
from openedx_filters.learning.filters import CourseStartDateValidationFailed, CoursewareAccessChecksRequested

# Courses whose start date equals DEFAULT_START_DATE are considered "unscheduled" in the platform.
# Messages for these courses omit the specific date and use a generic "has not started" wording.
try:
    from xmodule.course_metadata_utils import DEFAULT_START_DATE
except ImportError:
    DEFAULT_START_DATE = datetime(2040, 1, 1, tzinfo=ZoneInfo("UTC"))

from enterprise.models import EnterpriseCourseEnrollment, EnterpriseCustomerUser
from enterprise.utils import enterprise_learner_enrolled

log = logging.getLogger(__name__)

# Error code (for platform AccessError exceptions) representing a start date
# error with a hint that the enrollment is enterprise subsidized.  This hint is
# used by the Learning MFE to trigger enterprise redirect logic.
COURSE_NOT_STARTED_ENTERPRISE_LEARNER = "course_not_started_enterprise_learner"


class EnterpriseStartDateAccessFailureStep(PipelineStep):
    """
    Substitutes a more specific start-date access-error payload for enterprise learners.

    Registered against ``org.openedx.learning.course.start_date.validation_failed.v1``.
    Raises ``CourseStartDateValidationFailed.OverrideStartDateError`` when the request
    user is an enterprise learner enrolled via a subsidy for the given course. If the
    user is not an enterprise learner, the step is a no-op.
    """

    def run_filter(  # pylint: disable=arguments-differ
        self,
        course_key: CourseKey,
        start_date: datetime,
    ) -> dict:
        request = get_current_request()
        if request is None:
            return {"course_key": course_key, "start_date": start_date}
        user = request.user
        if not user.is_authenticated or not enterprise_learner_enrolled(request, course_key):
            return {"course_key": course_key, "start_date": start_date}

        # By now, all conditions have been met to warrant a custom enterprise-specific override error.
        if start_date == DEFAULT_START_DATE:
            developer_message = "Course has not started, and the learner is enrolled via an enterprise subsidy."
            user_message = "Course has not started"
        else:
            developer_message = (
                f"Course does not start until {start_date}, and the learner is enrolled via an enterprise subsidy."
            )
            user_message = f"Course does not start until {start_date:%B %d, %Y}"
        raise CourseStartDateValidationFailed.OverrideStartDateError(
            message="Course has not started, and this is an enterprise learner",
            error_code=COURSE_NOT_STARTED_ENTERPRISE_LEARNER,
            developer_message=developer_message,
            user_message=user_message,
        )


class ActiveEnterpriseCheckStep(PipelineStep):
    """
    Deny access when the learner's active EnterpriseCustomer differs from the
    EnterpriseCustomer attached to their EnterpriseCourseEnrollment for this course.

    Registered against ``org.openedx.learning.courseware.access_checks.requested.v1``.
    Raises ``CoursewareAccessChecksRequested.PreventCoursewareAccess`` to deny access.
    """

    def run_filter(self, user: Any, course_key: CourseKey) -> dict:  # pylint: disable=arguments-differ
        enterprise_enrollments = EnterpriseCourseEnrollment.objects.filter(
            course_id=course_key, enterprise_customer_user__user_id=user.id,
        )
        if not enterprise_enrollments.exists():
            return {"user": user, "course_key": course_key}

        try:
            active_ecu = EnterpriseCustomerUser.objects.get(user_id=user.id, active=True)
            if enterprise_enrollments.filter(enterprise_customer_user=active_ecu).exists():
                return {"user": user, "course_key": course_key}
            active_enterprise_name = active_ecu.enterprise_customer.name
        except (EnterpriseCustomerUser.DoesNotExist, EnterpriseCustomerUser.MultipleObjectsReturned):
            # Ideally this should not happen — there should be exactly 1 active enterprise customer.
            log.error("Multiple or No Active Enterprise found for the user %s.", user.id)
            active_enterprise_name = "Incorrect"

        enrollment_enterprise_name = (
            enterprise_enrollments.first().enterprise_customer_user.enterprise_customer.name
        )
        user_message = (
            f"You are enrolled in this course with '{enrollment_enterprise_name}'. However, you are "
            f"currently logged in as a '{active_enterprise_name}' user. Please log in with "
            f"'{enrollment_enterprise_name}' to access this course."
        )
        raise CoursewareAccessChecksRequested.PreventCoursewareAccess(
            message="Incorrect active enterprise",
            error_code="incorrect_active_enterprise",
            developer_message="User active enterprise should be same as EnterpriseCourseEnrollment enterprise.",
            user_message=user_message,
        )
