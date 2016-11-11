# -*- coding: utf-8 -*-
"""
Utility functions for enterprise app.
"""
from __future__ import absolute_import, unicode_literals


def get_available_idps():
    """
    Get available Identity Providers.

    Raises a ValueError if it third_party_auth app is not available.

    Return:
        a list of SAMLProviderConfig instances if third_party_auth app is available.
    """
    try:
        # We give a choice field to user only if SAMLProviderConfig is present, otherwise we show
        # an integer field, Since, we will be adding a custom enterprise admin so we will also be removing
        # this dependency.
        from third_party_auth.models import SAMLProviderConfig
        return SAMLProviderConfig.objects.current_set().filter(enabled=True).all()
    except ImportError:
        raise ValueError("SAMLProviderConfig is not available.")


def get_idp_choices():
    """
    Get a list of identity providers choices for enterprise customer.

    Return:
        A list of choices of all identity providers, None if it can not get any available identity provider.
    """
    first = [("", "-"*7)]
    try:
        return first + [(idp.idp_slug, idp.name) for idp in get_available_idps()]
    except ValueError:
        return None
