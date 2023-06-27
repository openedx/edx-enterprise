"""
Views for the ``enterprise-catalog-query`` API endpoint.
"""

from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from rest_framework import permissions
from rest_framework.authentication import SessionAuthentication
from rest_framework.pagination import PageNumberPagination

from enterprise import models
from enterprise.api.v1 import serializers
from enterprise.api.v1.views.base_views import EnterpriseReadOnlyModelViewSet


class ExpandDefaultPageSize(PageNumberPagination):
    """
    Expands page size for the API.
    Used to populate support-tools repo's provisioning form catalog query dropdown component.
    """
    page_size = 100


class EnterpriseCatalogQueryViewSet(EnterpriseReadOnlyModelViewSet):
    """
    API views for the ``enterprise_catalog_query`` API endpoint.
    """
    queryset = models.EnterpriseCatalogQuery.objects.all()
    serializer_class = serializers.EnterpriseCatalogQuerySerializer
    permission_classes = (permissions.IsAuthenticated, permissions.IsAdminUser,)
    authentication_classes = (JwtAuthentication, SessionAuthentication,)
    pagination_class = ExpandDefaultPageSize
