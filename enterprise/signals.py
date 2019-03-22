# -*- coding: utf-8 -*-
"""
Django signal handlers.
"""
from __future__ import absolute_import, unicode_literals

from logging import getLogger

from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from enterprise.constants import ENTERPRISE_LEARNER_ROLE
from enterprise.decorators import disable_for_loaddata
from enterprise.models import (
    EnterpriseCustomerCatalog,
    EnterpriseCustomerUser,
    PendingEnterpriseCustomerUser,
    SystemWideEnterpriseRole,
    SystemWideEnterpriseUserRoleAssignment,
)
from enterprise.utils import get_default_catalog_content_filter, track_enrollment

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
    pending_enrollments = list(pending_ecu.pendingenrollment_set.all())
    if pending_enrollments:
        def _complete_user_enrollment():  # pylint: disable=missing-docstring
            for enrollment in pending_enrollments:
                # EnterpriseCustomers may enroll users in courses before the users themselves
                # actually exist in the system; in such a case, the enrollment for each such
                # course is finalized when the user registers with the OpenEdX platform.
                enterprise_customer_user.enroll(
                    enrollment.course_id, enrollment.course_mode, cohort=enrollment.cohort_name)
                track_enrollment('pending-admin-enrollment', user_instance.id, enrollment.course_id)
            pending_ecu.delete()
        transaction.on_commit(_complete_user_enrollment)
    else:
        pending_ecu.delete()


@receiver(post_save, sender=EnterpriseCustomerCatalog, dispatch_uid='default_content_filter')
def default_content_filter(sender, instance, **kwargs):     # pylint: disable=unused-argument
    """
    Set default value for `EnterpriseCustomerCatalog.content_filter` if not already set.
    """
    if kwargs['created'] and not instance.content_filter:
        instance.content_filter = get_default_catalog_content_filter()
        instance.save()


@receiver(post_save, sender=EnterpriseCustomerUser)
def assign_enterprise_learner_role(sender, instance, **kwargs):     # pylint: disable=unused-argument
    """
    Assign an enterprise learner role to EnterpriseCustomerUser whenever a new record is created.
    """
    if kwargs['created'] and instance.user:
        enterprise_learner_role, __ = SystemWideEnterpriseRole.objects.get_or_create(name=ENTERPRISE_LEARNER_ROLE)
        SystemWideEnterpriseUserRoleAssignment.objects.get_or_create(
            user=instance.user,
            role=enterprise_learner_role
        )


@receiver(post_delete, sender=EnterpriseCustomerUser)
def delete_enterprise_learner_role_assignment(sender, instance, **kwargs):     # pylint: disable=unused-argument
    """
    Delete the associated enterprise learner role assignment record when deleting an EnterpriseCustomerUser record.
    """
    if instance.user:
        enterprise_learner_role, __ = SystemWideEnterpriseRole.objects.get_or_create(name=ENTERPRISE_LEARNER_ROLE)
        try:
            SystemWideEnterpriseUserRoleAssignment.objects.get(
                user=instance.user,
                role=enterprise_learner_role
            ).delete()
        except SystemWideEnterpriseUserRoleAssignment.DoesNotExist:
            # Do nothing if no role assignment is present for the enterprise customer user.
            pass
