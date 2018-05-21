# -*- coding: utf-8 -*-
"""
Views for enterprise api version 2 endpoint.
"""
from __future__ import absolute_import, unicode_literals

from logging import getLogger

from enterprise.api.v1 import serializers as v1_serializers, views as v1_views
from enterprise.api.v2 import serializers

LOGGER = getLogger(__name__)


class EnterpriseCustomerCatalogViewSet(v1_views.EnterpriseCustomerCatalogViewSet):
    """
    API views for performing search through course discovery at the ``enterprise_catalogs`` API version 2 endpoint.
    """

    def get_serializer_class(self):
        action = getattr(self, 'action', None)
        if action == 'retrieve':
            return serializers.EnterpriseCustomerCatalogDetailSerializer
        return v1_serializers.EnterpriseCustomerCatalogSerializer
