# -*- coding: utf-8 -*-
"""
Renderer(s) for api response.
"""
from __future__ import absolute_import, unicode_literals

from rest_framework.negotiation import DefaultContentNegotiation
from rest_framework.settings import api_settings


class IgnoreClientContentNegotiation(DefaultContentNegotiation):
    """
    Class for client content negotiation.
    """

    def select_renderer(self, request, renderers, format_suffix):  # pylint: disable=signature-differs
        # Allow URL style format override.  eg. "?format=json or http://example.com/v1/organizations.xml/
        render_format = format_suffix or request.query_params.get(api_settings.FORMAT_SUFFIX_KWARG)
        if render_format:
            return DefaultContentNegotiation.select_renderer(self, request, renderers, render_format)

        # Select the first renderer in the `.renderer_classes` list.
        return (renderers[0], renderers[0].media_type)
