# -*- coding: utf-8 -*-
"""
Helper functions for enterprise app.
"""

from enterprise.models import EnterpriseCustomerBrandingConfiguration


def get_enterprise_branding_info(provider_id=None):
    """
    Return the EnterpriseCustomer branding information.
    """
    return EnterpriseCustomerBrandingConfiguration.objects.filter(
        enterprise_customer__identity_provider=provider_id
    ).first()
