# -*- coding: utf-8 -*-
"""
Helper functions for enterprise app.
"""
from __future__ import absolute_import, unicode_literals

from enterprise.models import EnterpriseCustomerBrandingConfiguration


def get_enterprise_branding_info_by_provider_id(provider_id=None):  # pylint: disable=invalid-name
    """
    Return the EnterpriseCustomer branding information based on provider_id.

    Provider_id: There is 1:1 relation b/w EnterpriseCustomer and Identity provider.
    """
    return EnterpriseCustomerBrandingConfiguration.objects.filter(
        enterprise_customer__enterprise_customer_identity_provider__provider_id=provider_id
    ).first()


def get_enterprise_branding_info_by_ec_uuid(ec_uuid=None):  # pylint: disable=invalid-name
    """
    Return the EnterpriseCustomer branding information based on enterprise customer uuid.
    """
    return EnterpriseCustomerBrandingConfiguration.objects.filter(
        enterprise_customer__uuid=ec_uuid
    ).first()
