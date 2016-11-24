# -*- coding: utf-8 -*-
"""
Utility functions for enterprise app.
"""
from __future__ import absolute_import, unicode_literals

from functools import wraps

try:
    # Try to import identity provider registry if third_party_auth is present
    from third_party_auth.provider import Registry
except ImportError:
    Registry = None

USER_POST_SAVE_DISPATCH_UID = "user_post_save_upgrade_pending_enterprise_customer_user"


def get_identity_provider(provider_id):
    """
    Get Identity Provider with given id.

    Raises a ValueError if it third_party_auth app is not available.

    Return:
        Instance of ProviderConfig or None.
    """
    return Registry and Registry.get(provider_id)


def get_idp_choices():
    """
    Get a list of identity providers choices for enterprise customer.

    Return:
        A list of choices of all identity providers, None if it can not get any available identity provider.
    """
    first = [("", "-"*7)]
    if Registry:
        return first + [(idp.provider_id, idp.name) for idp in Registry.enabled()]
    else:
        return None


def get_all_field_names(model):
    """
    Return all fields' names from a model.

    According to `Django documentation`_, ``get_all_field_names`` should become some monstrosity with chained
    iterable ternary nested in a list comprehension. For now, a simpler version of iterating over fields and
    getting their names work, but we might have to switch to full version in future.

    .. _Django documentation: https://docs.djangoproject.com/en/1.8/ref/models/meta/
    """
    return [f.name for f in model._meta.get_fields()]


def disable_for_loaddata(signal_handler):
    """
    Decorator that turns off signal handlers when loading fixture data.

    Django docs instruct to avoid further changes to the DB if raw=True as it might not be in a consistent state.
    See https://docs.djangoproject.com/en/dev/ref/signals/#post-save
    """
    # http://stackoverflow.com/a/15625121/882918
    @wraps(signal_handler)
    def wrapper(*args, **kwargs):
        """
        Function wrapper.
        """
        if kwargs.get('raw', False):
            return
        signal_handler(*args, **kwargs)
    return wrapper
