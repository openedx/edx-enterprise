# -*- coding: utf-8 -*-
"""
Utility functions for enterprise app.
"""
from __future__ import absolute_import, unicode_literals

import logging
import os
import re
from functools import wraps

from django.conf import settings

try:
    from edxmako.paths import add_lookup
except ImportError:
    add_lookup = None

try:
    # Try to import identity provider registry if third_party_auth is present
    from third_party_auth.provider import Registry
except ImportError:
    Registry = None


LOGGER = logging.getLogger(__name__)


class NotConnectedToEdX(Exception):
    """
    Exception to raise when not connected to OpenEdX.

    In general, this exception shouldn't be raised, because this package is
    designed to be installed directly inside an existing OpenEdX platform.
    """

    def __init__(self, *args, **kwargs):
        """
        Log a warning and initialize the exception.
        """
        LOGGER.warning('edx-enterprise unexpectedly failed as if not installed in an OpenEdX platform')
        super(NotConnectedToEdX, self).__init__(*args, **kwargs)


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


def null_decorator(func):
    """
    Decorator that does nothing to the wrapped function.

    If we're unable to import social.pipeline.partial, which is the case in our CI platform,
    we need to be able to wrap the function with something.
    """
    return func


def patch_mako_lookup():
    """
    Update the EdX Mako paths to point to our consent template.

    Do nothing if we're not connected to OpenEdX.
    """
    if add_lookup is None:
        return
    full_location = os.path.realpath(__file__)
    directory = os.path.dirname(full_location)
    template_location = os.path.join(directory, 'templates', 'enterprise')
    # Both add an item to the setting AND insert the lookup for immediate use
    settings.MAKO_TEMPLATES['main'].insert(0, template_location)
    add_lookup('main', template_location)


def get_catalog_admin_url(catalog_id):
    """
    Get url to catalog details admin page.

    Arguments:
        catalog_id (int): Catalog id for which to return catalog details url.

    Returns:
         URL pointing to catalog details admin page for the give catalog id.

    Example:
        >>> get_catalog_admin_url_template(2)
        "http://localhost:18381/admin/catalogs/catalog/2/change/"
    """
    return get_catalog_admin_url_template().format(catalog_id=catalog_id)


def get_catalog_admin_url_template():
    """
    Get template of catalog admin url.

    URL template will contain a placeholder '{catalog_id}' for catalog id.

    Returns:
        A string containing template for catalog url.

    Example:
        >>> get_catalog_admin_url_template()
        "http://localhost:18381/admin/catalogs/catalog/{catalog_id}/change/"
    """
    api_base_url = getattr(settings, "COURSE_CATALOG_API_URL", "")

    # Extract FQDN (Fully Qualified Domain Name) from API URL.
    match = re.match(r"^(?P<fqdn>(?:https?://)?[^/]+)", api_base_url)

    if not match:
        return ""

    # Return matched FQDN from catalog api url appended with catalog admin path
    return match.group("fqdn").rstrip("/") + "/admin/catalogs/catalog/{catalog_id}/change/"
