# -*- coding: utf-8 -*-
"""
Utility functions for the Enterprise API.
"""
from __future__ import absolute_import, unicode_literals

from django.conf import settings

from enterprise.models import (
    EnterpriseCustomerCatalog,
    EnterpriseCustomerReportingConfiguration,
    EnterpriseCustomerUser,
)

SERVICE_USERNAMES = (
    'ECOMMERCE_SERVICE_WORKER_USERNAME',
    'ENTERPRISE_SERVICE_WORKER_USERNAME'
)


def get_service_usernames():
    """
    Return the set of service usernames that are given extended permissions in the API.
    """
    return {getattr(settings, username, None) for username in SERVICE_USERNAMES}


def get_enterprise_customer_from_catalog_id(catalog_id):
    """
    Get the enterprise customer id given an enterprise customer catalog id.
    """
    try:
        return str(EnterpriseCustomerCatalog.objects.get(pk=catalog_id).enterprise_customer.uuid)
    except EnterpriseCustomerCatalog.DoesNotExist:
        return None


def get_ent_cust_from_report_config_uuid(uuid):
    """
    Get the enterprise customer id given an enterprise report configuration UUID.
    """
    try:
        return str(EnterpriseCustomerReportingConfiguration.objects.get(uuid=uuid).enterprise_customer.uuid)
    except EnterpriseCustomerReportingConfiguration.DoesNotExist:
        return None


def get_enterprise_customer_from_user_id(user_id):
    """
    Get the enterprise customer id given an user id
    """
    try:
        return str(EnterpriseCustomerUser.objects.get(user_id=user_id).enterprise_customer.uuid)
    except EnterpriseCustomerUser.DoesNotExist:
        return None
