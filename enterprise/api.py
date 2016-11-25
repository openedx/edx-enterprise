# -*- coding: utf-8 -*-
"""
Helper functions for enterprise app.
"""
from __future__ import absolute_import, unicode_literals

from enterprise.models import EnterpriseCustomerBrandingConfiguration


def get_enterprise_branding_info(provider_id=None):
    """
    Return the EnterpriseCustomer branding information.
    """
    return EnterpriseCustomerBrandingConfiguration.objects.filter(
        enterprise_customer__enterprise_customer_identity_provider__provider_id=provider_id
    ).first()
