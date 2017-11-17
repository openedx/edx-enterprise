# -*- coding: utf-8 -*-
"""
Django signal handlers.
"""
from __future__ import absolute_import, unicode_literals

from logging import getLogger

from enterprise.decorators import disable_for_loaddata
from enterprise.models import EnterpriseCourseEnrollment, EnterpriseCustomerUser, PendingEnterpriseCustomerUser
from enterprise.utils import track_enrollment

logger = getLogger(__name__)  # pylint: disable=invalid-name


@disable_for_loaddata
def handle_user_post_save(sender, **kwargs):  # pylint: disable=unused-argument
    """
    Handle User model changes - checks if pending enterprise customer user record exists and upgrades it to actual link.

    If there are pending enrollments attached to the PendingEnterpriseCustomerUser, then this signal also takes the
    newly-created users and enrolls them in the relevant courses.
    """
    created = kwargs.get("created", False)
    user_instance = kwargs.get("instance", None)

    if user_instance is None:
        return  # should never happen, but better safe than 500 error

    try:
        pending_ecu = PendingEnterpriseCustomerUser.objects.get(user_email=user_instance.email)
    except PendingEnterpriseCustomerUser.DoesNotExist:
        return  # nothing to do in this case

    if not created:
        # existing user changed his email to match one of pending link records - try linking him to EC
        try:
            existing_record = EnterpriseCustomerUser.objects.get(user_id=user_instance.id)
            message_template = "User {user} have changed email to match pending Enterprise Customer link, " \
                               "but was already linked to Enterprise Customer {enterprise_customer} - " \
                               "deleting pending link record"
            logger.info(message_template.format(
                user=user_instance, enterprise_customer=existing_record.enterprise_customer
            ))
            pending_ecu.delete()
            return
        except EnterpriseCustomerUser.DoesNotExist:
            pass  # everything ok - current user is not linked to other ECs

    enterprise_customer_user = EnterpriseCustomerUser.objects.create(
        enterprise_customer=pending_ecu.enterprise_customer,
        user_id=user_instance.id
    )
    for enrollment in pending_ecu.pendingenrollment_set.all():
        # EnterpriseCustomers may enroll users in courses before the users themselves
        # actually exist in the system; in such a case, the enrollment for each such
        # course is finalized when the user registers with the OpenEdX platform.
        enrollment.complete_enrollment()
        EnterpriseCourseEnrollment.objects.create(
            enterprise_customer_user=enterprise_customer_user,
            course_id=enrollment.course_id,
        )
        track_enrollment('pending-admin-enrollment', user_instance.id, enrollment.course_id)
    pending_ecu.delete()
