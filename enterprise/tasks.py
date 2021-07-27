# -*- coding: utf-8 -*-
"""
Django tasks.
"""

from django.core import mail
from enterprise.utils import send_email_notification_message
from logging import getLogger

from celery import shared_task
from edx_django_utils.monitoring import set_code_owner_attribute

from django.db import IntegrityError

from enterprise.models import (
    EnterpriseCourseEnrollment,
    EnterpriseCustomerUser,
    EnterpriseEnrollmentSource,
)

LOGGER = getLogger(__name__)


@shared_task
@set_code_owner_attribute
def notify_enrolled_learners(
    enterprise_customer_uuid,
    admin_enrollment,
    email_items,
):
    """
    Send enrollment notifications to specified learners

    Arguments:
        * email_items: list of dictionary objects with fields:
        *
        *   enterprise_customer_uuid (string)
        *   course_id (string)
        *   user (dict) : one of the formats:
              - 1: { 'first_name': name, 'username': user_name, 'email': email } (similar to a User object)
              - 2: { 'user_email' : user_email } (similar to a PendingEnterpriseCustomerUser object)
        *   admin_enrollment=False : If True, this indicates admin based enrollment (e.g., bulk enrollment)
    """
    with mail.get_connection() as email_conn:
        for item in email_items:
            send_email_notification_message(
                item['user'],
                item['enrolled_in'],
                item['dashboard_url'],
                enterprise_customer_uuid,
                email_connection=email_conn,
                admin_enrollment=admin_enrollment,
            )


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

        try:
            EnterpriseCourseEnrollment.objects.get_or_create(
                course_id=course_id,
                enterprise_customer_user=enterprise_customer_user,
                defaults={
                    'source': EnterpriseEnrollmentSource.get_source(EnterpriseEnrollmentSource.ENROLLMENT_TASK),
                }
            )
        except IntegrityError:
            LOGGER.exception(
                "IntegrityError on attempt at EnterpriseCourseEnrollment for user with id [%s] "
                "and course id [%s]", enterprise_customer_user.user_id, course_id,
            )
