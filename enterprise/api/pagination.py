"""
Pagination helpers for enterprise api.
"""
from __future__ import absolute_import, unicode_literals

from collections import OrderedDict

from rest_framework.response import Response

from six.moves.urllib.parse import urlparse  # pylint: disable=import-error


def get_paginated_response(data, request):
    """
    Update pagination links in course catalog data and return DRF Response.

    Arguments:
        data (dict): Dictionary containing catalog courses.
        request (HttpRequest): Current request object.

    Returns:
        (Response): DRF response object containing pagination links.
    """
    url = request.build_absolute_uri().rstrip('/') + '/'
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
