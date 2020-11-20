# -*- coding: utf-8 -*-
"""
Django tasks.
"""

from logging import getLogger

from celery import shared_task
from edx_django_utils.monitoring import set_code_owner_attribute

from enterprise.models import EnterpriseCourseEnrollment, EnterpriseCustomerUser, EnterpriseEnrollmentSource

LOGGER = getLogger(__name__)


@shared_task
@set_code_owner_attribute
def create_enterprise_enrollment(course_id, enterprise_customer_user_id):
    """
    Create enterprise enrollment for user if course_id part of catalog for the ENT customer.
    """
    enterprise_customer_user = EnterpriseCustomerUser.objects.get(
        id=enterprise_customer_user_id
    )
    # Prevent duplicate records from being created if possible
    # before we need to make a call to discovery
    if EnterpriseCourseEnrollment.objects.filter(
            enterprise_customer_user=enterprise_customer_user,
            course_id=course_id,
    ).exists():
        LOGGER.info((
            "EnterpriseCourseEnrollment record exists for user %s "
            "on course %s. Exiting task."
        ), enterprise_customer_user.user_id, course_id)
        return

    enterprise_customer = enterprise_customer_user.enterprise_customer
    if enterprise_customer.catalog_contains_course(course_id):
        LOGGER.info((
            "Creating EnterpriseCourseEnrollment for user %s "
            "on course %s for enterprise_customer %s"
        ), enterprise_customer_user.user_id, course_id, enterprise_customer)

        # On Create we set the Source to be ENROLLMENT_TASK here.  This Source
        # is generalized from being just a B2C Source type because it is possible
        # to reach this task before the EnterpriseCustomerEnrollment is created
        # depending on timing.
        #
        # We have made changes elsewhere to avoid this issue, but in the mean time
        # we believe a Source of ENROLLMENT_TASK is more clear.

        EnterpriseCourseEnrollment.objects.create(
            course_id=course_id,
            enterprise_customer_user=enterprise_customer_user,
            source=EnterpriseEnrollmentSource.get_source(EnterpriseEnrollmentSource.ENROLLMENT_TASK)
        )
