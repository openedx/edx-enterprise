"""
Views for the ``enterprise-customer-user`` API endpoint.
"""
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters

from enterprise import models
from enterprise.api.filters import EnterpriseCustomerUserFilterBackend
from enterprise.api.pagination import PaginationWithFeatureFlags
from enterprise.api.v1 import serializers
from enterprise.api.v1.views.base_views import EnterpriseReadWriteModelViewSet


class EnterpriseCustomerUserViewSet(EnterpriseReadWriteModelViewSet):
    """
    API views for the ``enterprise-learner`` API endpoint.
    """

    queryset = models.EnterpriseCustomerUser.objects.all()
    filter_backends = (filters.OrderingFilter, DjangoFilterBackend, EnterpriseCustomerUserFilterBackend)
    pagination_class = PaginationWithFeatureFlags

    FIELDS = (
        'enterprise_customer', 'user_id', 'active',
    )
    filterset_fields = FIELDS
    ordering_fields = FIELDS

    def get_serializer_class(self):
        """
        Use a flat serializer for any requests that aren't read-only.
        """
        if self.request.method in ('GET',):
            return serializers.EnterpriseCustomerUserReadOnlySerializer

        return serializers.EnterpriseCustomerUserWriteSerializer
