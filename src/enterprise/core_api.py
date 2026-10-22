"""
Core Python API for the enterprise app.

These are core enterprise utility functions that rely on access to enterprise models or data.

Important: ``models.py`` files should NEVER import this module, since that would create an import cycle.
"""
from opaque_keys.edx.keys import CourseKey

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.http import HttpRequest

from enterprise.logging import getEnterpriseLogger
from enterprise.models import EnterpriseCourseEnrollment, EnterpriseCustomerUser

# In ENT-11576, enterprise_customer_from_session_or_learner_data will be migrated into this repo.
try:
    from openedx.features.enterprise_support.api import enterprise_customer_from_session_or_learner_data
except ImportError:
    enterprise_customer_from_session_or_learner_data = None

LOGGER = getEnterpriseLogger(__name__)


def get_active_enterprise_customer_user(user: AbstractUser) -> EnterpriseCustomerUser | None:
    """
    Return the active EnterpriseCustomerUser model instance for ``user``, or None.

    There is at most one active EnterpriseCustomerUser per user.
    """
    if not getattr(settings, 'ENABLE_ENTERPRISE_INTEGRATION', False) or not user.is_authenticated:
        return None
    try:
        return EnterpriseCustomerUser.objects.get(user_id=user.id, active=True)
    except EnterpriseCustomerUser.DoesNotExist:
        LOGGER.info(
            "Active EnterpriseCustomerUser for user [%s] does not exist", user.username,
        )
        return None


def enterprise_learner_enrolled(request: HttpRequest, course_key: CourseKey) -> bool:
    """
    Return True if the request user is an enterprise learner enrolled via a subsidy for ``course_key``.

    Returns True only when all of the following conditions hold:

    1. The request user has an active linked EnterpriseCustomer.
    2. The linked customer has the learner portal enabled.
    3. The user has an EnterpriseCourseEnrollment for ``course_key`` under that customer.

    Intended use: determining whether the learner should be subject to enterprise-specific
    courseware gating (e.g. data-sharing consent enforcement or start-date error overrides)
    and redirected to the enterprise learner portal when access is denied.

    ``enterprise_customer_from_session_or_learner_data`` is used in lieu of direct model access
    because it caches the customer data on the request session, making it safe to call on
    frequently-hit views without incurring repeated database queries.
    """
    # enterprise_customer is either None (learner not linked to any customer) or a serialized
    # EnterpriseCustomer representing the learner's active linked customer.
    enterprise_customer = enterprise_customer_from_session_or_learner_data(request)

    enterprise_enrollment_exists = False

    # 1. Check that the request user has an active linked EnterpriseCustomer.
    if enterprise_customer:
        # 2. Check that the linked customer has the learner portal enabled.
        if enterprise_customer.get('enable_learner_portal'):
            # 3. Make sure the enterprise learner is actually enrolled in the requested course,
            #    subsidized via the discovered customer.
            enterprise_enrollment_exists = EnterpriseCourseEnrollment.objects.filter(
                course_id=course_key,
                enterprise_customer_user__user_id=request.user.id,
                enterprise_customer_user__enterprise_customer__uuid=enterprise_customer['uuid'],
            ).exists()

    LOGGER.info(
        (
            "[enterprise_learner_enrolled] Checking for an enterprise enrollment for "
            "lms_user_id=%s in course_key=%s via enterprise_customer_uuid=%s (enable_learner_portal=%s). "
            "Exists: %s"
        ),
        request.user.id,
        course_key,
        enterprise_customer['uuid'] if enterprise_customer else None,
        enterprise_customer.get('enable_learner_portal') if enterprise_customer else None,
        enterprise_enrollment_exists,
    )
    return enterprise_enrollment_exists
