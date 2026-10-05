"""
Pluggable override implementation for the programs API.
"""
from django.contrib.auth.models import AbstractBaseUser

from enterprise.models import EnterpriseCourseEnrollment


def enterprise_get_enterprise_course_ids(
    prev_fn,  # pylint: disable=unused-argument
    enterprise_uuid: str,
    user: AbstractBaseUser,
) -> list[str]:
    """
    Return course IDs the given user is enterprise-enrolled in for the given enterprise customer.

    This allows the platform's programs list endpoint (`GET /api/dashboard/v1/programs/{enterprise_uuid}/`)
    to narrow a learner's enrollments down to a single enterprise customer.

    Pluggable override hook point:
    - hook function: `get_enterprise_course_ids()`
    - platform path: `openedx/core/djangoapps/programs/rest_api/v1/views.py`

    Arguments:
        prev_fn: the previous (default) implementation. Unused.
        enterprise_uuid (str): UUID of the enterprise customer to filter enrollments by.
        user: the Django User object.

    Returns:
        list of str: course IDs (specifically, course keys) of the user's enrollments
        under the given enterprise customer. Empty when the user has no such enrollments.
    """
    return list(
        EnterpriseCourseEnrollment.objects.filter(
            enterprise_customer_user__user_id=user.id,
            enterprise_customer_user__enterprise_customer__uuid=enterprise_uuid,
        ).values_list("course_id", flat=True)
    )
