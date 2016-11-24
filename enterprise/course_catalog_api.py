# -*- coding: utf-8 -*-
"""
Utilities to get details from the course catalog API.
"""
from __future__ import absolute_import, unicode_literals

from django.utils.translation import ugettext_lazy as _

try:
    from openedx.core.djangoapps.api_admin.utils import course_discovery_api_client
except ImportError:
    course_discovery_api_client = None

try:
    from openedx.core.djangoapps.catalog.models import CatalogIntegration
except ImportError:
    CatalogIntegration = None

try:
    from openedx.core.lib.edx_api_utils import get_edx_api_data
except ImportError:
    get_edx_api_data = None


class NotConnectedToOpenEdX(Exception):
    """
    Exception to raise when we weren't able to import needed resources.

    This is raised when we try to use the resources, rather than on
    import, so that during testing we can load the module
    and mock out the resources we need.
    """

    pass


def get_catalog_api_client(user):
    """
    Retrieve a course catalog API client.

    This method retrieves an authenticated API client that can be used
    to access the course catalog API. It raises an exception to be caught at
    a higher level if the package doesn't have OpenEdX resources available.
    """
    if course_discovery_api_client is None:
        raise NotConnectedToOpenEdX(
            _('To get a catalog API client, this package must be installed in an OpenEdX environment.')
        )
    else:
        return course_discovery_api_client(user)


def get_all_catalogs(user):
    """
    Return a list of all course catalogs, including name and ID.
    """
    client = get_catalog_api_client(user)
    if CatalogIntegration is None:
        raise NotConnectedToOpenEdX(
            _('To get a CatalogIntegration object, this package must be installed in an OpenEdX environment.')
        )
    if get_edx_api_data is None:
        raise NotConnectedToOpenEdX(
            _('To parse a catalog API response, this package must be installed in an OpenEdX environment.')
        )
    return get_edx_api_data(
        CatalogIntegration.current(),
        user,
        'catalogs',
        api=client,
    )
