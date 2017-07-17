# -*- coding: utf-8 -*-
"""
Helper functions for the Consent application.
"""

from __future__ import absolute_import, unicode_literals

from django.contrib.auth.models import User

# Will be using internal models at a later time.
from enterprise.models import (
    EnterpriseCourseEnrollment,
    EnterpriseCustomer,
    EnterpriseCustomerUser,
    UserDataSharingConsentAudit,
)


def consent_exists(user_id, course_id, enterprise_customer_uuid):
    """
    Get whether any consent is associated with an ``EnterpriseCustomer``.

    :param user_id: The user that grants consent.
    :param course_id: The course for which consent is granted.
    :param enterprise_customer_uuid: The consent requester.
    :return: Whether any consent (provided or unprovided) exists.
    """
    enterprise_customer = get_enterprise_customer(enterprise_customer_uuid)
    enterprise_course_enrollment = get_enterprise_course_enrollment(user_id, course_id, enterprise_customer)
    return bool(enterprise_course_enrollment or get_user_dsc_audit(user_id, enterprise_customer))


def consent_provided(user_id, course_id, enterprise_customer_uuid):
    """
    Get whether consent is provided by the user to the Enterprise customer.

    :param user_id: The user that grants consent.
    :param course_id: The course for which consent is granted.
    :param enterprise_customer_uuid: The consent requester.
    :return: Whether consent is provided to the Enterprise customer by the user for a course.
    """
    enterprise_customer = get_enterprise_customer(enterprise_customer_uuid)
    enterprise_course_enrollment = get_enterprise_course_enrollment(user_id, course_id, enterprise_customer)
    provided = enterprise_course_enrollment is not None and enterprise_course_enrollment.consent_available

    if enterprise_course_enrollment is None:
        user_data_consent_audit = get_user_dsc_audit(user_id, enterprise_customer)
        provided = user_data_consent_audit is not None and user_data_consent_audit.enabled

    return provided


def consent_required(user_id, course_id, enterprise_customer_uuid):
    """
    Get whether consent is required by the ``EnterpriseCustomer``.

    :param user_id: The user that grants consent.
    :param course_id: The course for which consent is granted.
    :param enterprise_customer_uuid: The consent requester.
    :return: Whether consent is required for a course by an Enterprise customer from a user.
    """
    if consent_provided(user_id, course_id, enterprise_customer_uuid):
        return False

    enterprise_customer = get_enterprise_customer(enterprise_customer_uuid)
    return enterprise_customer is not None and enterprise_customer.enforces_data_sharing_consent('at_enrollment')


def get_user_id(username):
    """
    Get the ID of the ``User`` associated with ``username``.

    :param username: The username of the ``User`` from whom to get the ID.
    :return: The ID of the user.
    """
    try:
        return User.objects.get(username=username).pk
    except User.DoesNotExist:
        return None


def get_enterprise_customer(uuid):
    """
    Get the ``EnterpriseCustomer`` instance associated with ``uuid``.

    :param uuid: The universally unique ID of the enterprise customer.
    :return: The ``EnterpriseCustomer`` instance, or ``None`` if it doesn't exist.
    """
    try:
        return EnterpriseCustomer.objects.get(uuid=uuid)  # pylint: disable=no-member
    except EnterpriseCustomer.DoesNotExist:
        return None


def get_enterprise_customer_user(enterprise_customer, user_id):
    """
    Get the ``EnterpriseCustomerUser`` instance associated with params.

    :param enterprise_customer: The ``EnterpriseCustomer`` associated with this user.
    :param user_id: The ID of the user.
    :return: The ``EnterpriseCustomerUser`` instance, or ``None`` if it doesn't exist.
    """
    try:
        return EnterpriseCustomerUser.objects.get(
            enterprise_customer=enterprise_customer,
            user_id=user_id
        )
    except EnterpriseCustomerUser.DoesNotExist:
        return None


def get_enterprise_course_enrollment(user_id, course_id, enterprise_customer):
    """
    Get the ``EnterpriseCourseEnrollment`` instance associated with params.

    :param user_id: The ID of the user.
    :param course_id: The ID of the course.
    :param enterprise_customer: The ``EnterpriseCustomer`` associated with the user and course.
    :return: The ``EnterpriseCourseEnrollment`` instance, or ``None`` if it doesn't exist.
    """
    try:
        return EnterpriseCourseEnrollment.objects.get(
            enterprise_customer_user__enterprise_customer=enterprise_customer,
            enterprise_customer_user__user_id=user_id,
            course_id=course_id
        )
    except EnterpriseCourseEnrollment.DoesNotExist:
        return None


def get_user_dsc_audit(user_id, enterprise_customer):
    """
    Get the ``UserDataSharingConsentAudit`` instance associated with params.

    :param user_id: The ID of the user.
    :param course_id: The ID of the course.
    :param enterprise_customer: The EnterpriseCustomer associated with the user.
    :return: The ``UserDataSharingConsentAudit`` instance, or ``None`` if it doesn't exist.
    """
    try:
        return UserDataSharingConsentAudit.objects.get(
            user__enterprise_customer=enterprise_customer,
            user__user_id=user_id
        )
    except UserDataSharingConsentAudit.DoesNotExist:
        return None
