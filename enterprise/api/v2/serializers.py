# -*- coding: utf-8 -*-
"""
Serializers for enterprise api version 2.
"""

from __future__ import absolute_import, unicode_literals

from enterprise.api.v1 import serializers as v1_serializers


class EnterpriseCustomerCatalogDetailSerializer(v1_serializers.EnterpriseCustomerCatalogDetailSerializer):
    """
    Serializer for the ``EnterpriseCustomerCatalog`` model which includes
    the catalog's discovery service search query results.
    """

    COURSE_DISCOVERY_CLIENT_VERSION = 'v2'
