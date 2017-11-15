# -*- coding: utf-8 -*-
"""
Utility functions for enterprise app.
"""
from __future__ import absolute_import, unicode_literals

import logging

import rules

from enterprise.models import EnterpriseCustomer, EnterpriseCustomerUser, EnterpriseCourseEnrollment

LOGGER = logging.getLogger(__name__)


ENTERPRISE_ADMIN_EDIT_PERMISSIONS = [
    'enterprise.{}_enterprisecustomer',
    'enterprise.{}_enterprisecustomeruser',
    'enterprise.{}_pendingenterprisecustomeruser',
    'enterprise.{}_enterprisecustomerbrandingconfiguration',
    'enterprise.{}_enterprisecustomeridentityprovider',
    'enterprise.{}_enterprisecustomerentitlement',
    'enterprise.{}_enterprisecourseenrollment',
    'enterprise.{}_enterprisecustomercatalog',
    'enterprise.{}_enterprisecustomerreportingconfiguration',
    'enterprise.{}_pendingenrollment',
]

ENTERPRISE_ADMIN_VIEW_PERMISSIONS = [
    'enterprise.view_enterprisecustomeruser',
    'enterprise.view_pendingenterprisecustomeruser',
    'enterprise.view_enterprisecourseenrollment',
    'enterprise.view_enterprisecustomerreportingconfiguration',
    'enterprise.view_pendingenrollment',
]

ENTERPRISE_VIEW_PERMISSIONS = [
    'enterprise.view_enterprisecustomer',
    'enterprise.view_enterprisecustomerbrandingconfiguration',
    'enterprise.view_enterprisecustomeridentityprovider',
    'enterprise.view_enterprisecustomerentitlement',
    'enterprise.view_enterprisecustomercatalog',
]


@rules.predicate
def has_view_access_to_enterprise_object(user, enterprise_object):
    """
    Checks basic view access to an enterprise object.

    This is meant for enterprise objects that do not need view restrictions beyond being linked to a common enterprise.

    Because there is filtering on the endpoints that would use this, we return True if no object is passed,
    trusting that the filtering will only reveal objects that are also linked to the same enterprise.

    If the user is staff or is linked to the enterprise object, return True. Otherwise, return False.
    """
    if not enterprise_object:
        return True
    elif user.is_staff or is_linked_to_enterprise_object(user, enterprise_object):
        return True
    else:
        return False


@rules.predicate
def has_admin_view_access_to_enterprise_object(user, enterprise_object):
    """
    Checks view access for enterprise objects that should only be viewable by admins or owners of the object.

    We return None instead of True in order to fall back on the django authentication framework checks. This happens
    if no object is passed (it is a model level permission check) or if the user is linked to the enterprise or is
    staff, in which case we need to check the model level permission.

    If the user is asking for access to their EnterpriseCustomerUser or any object tied to an EnterpriseCustomerUser
    model, we return True if the users match (they are the owner of the object).
    """
    if not enterprise_object:
        return None
    elif is_owner_of_enterprise_object(user, enterprise_object):
        return True
    elif user.is_staff or is_linked_to_enterprise_object(user, enterprise_object):
        return None
    else:
        return False


@rules.predicate
def has_admin_edit_access_to_enterprise_object(user, enterprise_object):
    """
    Checks edit (add, change, delete) access to an enterprise object.

    This falls back on the django authentication model permission check by returning None if no particular object
    was specified or if the user is staff or linked to the enterprise customer.
    """
    if not enterprise_object:
        return None
    elif user.is_staff or is_linked_to_enterprise_object(user, enterprise_object):
        return None
    else:
        return False


@rules.predicate
def is_linked_to_enterprise_object(user, enterprise_object):
    """
    Check if the user is an EnterpriseCustomerUser of the same enterprise as the passed in object.

    If the object is None, we return False.
    """
    if not enterprise_object:
        return False
    try:
        enterprise_customer_user = get_enterprise_customer_user(user, enterprise_object)
        if enterprise_customer_user:
            return True
    except EnterpriseCustomerUser.DoesNotExist:
        pass

    return False


@rules.predicate
def is_owner_of_enterprise_object(user, enterprise_object):
    """
    Check if the user is the same EnterpriseCustomerUser as the enterprise object or the user linked to the object.

    If the object is None, we return False.
    """
    if not enterprise_object:
        return False
    try:
        enterprise_customer_user = get_enterprise_customer_user(user, enterprise_object)
        if enterprise_customer_user:
            if enterprise_customer_user == enterprise_object:
                return True
            elif (isinstance(enterprise_object, EnterpriseCourseEnrollment) and
                  enterprise_object.enterprise_customer_user == enterprise_customer_user):
                return True
            else:
                return False
    except EnterpriseCustomerUser.DoesNotExist:
        pass

    return False


def get_enterprise_customer_user(user, enterprise_object):
    if isinstance(enterprise_object, EnterpriseCustomer):
        enterprise_customer = enterprise_object
    else:
        enterprise_customer = enterprise_object.enterprise_customer

    return EnterpriseCustomerUser.objects.get(
        user_id=user.id,
        enterprise_customer=enterprise_customer,
    )


for permission in ENTERPRISE_ADMIN_EDIT_PERMISSIONS:
    rules.add_perm(permission.format('add'), has_admin_edit_access_to_enterprise_object)
    rules.add_perm(permission.format('change'), has_admin_edit_access_to_enterprise_object)
    rules.add_perm(permission.format('delete'), has_admin_edit_access_to_enterprise_object)

for permission in ENTERPRISE_ADMIN_VIEW_PERMISSIONS:
    rules.add_perm(permission, has_admin_view_access_to_enterprise_object)

for permission in ENTERPRISE_VIEW_PERMISSIONS:
    rules.add_perm(permission, has_view_access_to_enterprise_object)
