"""
Pagination helpers for enterprise api.
"""

from collections import OrderedDict
from urllib.parse import urlparse

from edx_rest_framework_extensions.paginators import DefaultPagination
from rest_framework.response import Response

from enterprise.toggles import enterprise_features


class PaginationWithFeatureFlags(DefaultPagination):
    """
    Adds a ``features`` dictionary to the default paginated response
    provided by edx_rest_framework_extensions. The ``features`` dict
    represents a collection of Waffle-based feature flags/samples/switches
    that may be used to control whether certain aspects of the system are
    enabled or disabled (e.g., feature flag turned on for all staff users but
    not turned on for real customers/learners).
    """

    def get_paginated_response(self, data):
        """
        Modifies the default paginated response to include ``enterprise_features`` dict.

        Arguments:
            self: PaginationWithFeatureFlags instance.
            data (dict): Results for current page.

        Returns:
            (Response): DRF response object containing ``enterprise_features`` dict.
        """
        paginated_response = super().get_paginated_response(data)
        paginated_response.data.update({
            'enterprise_features': enterprise_features(),
        })
        return paginated_response


def get_paginated_response(data, request):
    """
    Update pagination links in course catalog data and return DRF Response.

    Arguments:
        data (dict): Dictionary containing catalog courses.
        request (HttpRequest): Current request object.

    Returns:
        (Response): DRF response object containing pagination links.
    """
    url = urlparse(request.build_absolute_uri())._replace(query=None).geturl()

    next_page = None
    previous_page = None

    if data['next']:
        next_page = "{base_url}?{query_parameters}".format(
            base_url=url,
            query_parameters=urlparse(data['next']).query,
        )
        next_page = next_page.rstrip('?')
    if data['previous']:
        previous_page = "{base_url}?{query_parameters}".format(
            base_url=url,
            query_parameters=urlparse(data['previous'] or "").query,
        )
        previous_page = previous_page.rstrip('?')

    return Response(OrderedDict([
        ('count', data['count']),
        ('next', next_page),
        ('previous', previous_page),
        ('results', data['results'])
    ]))
