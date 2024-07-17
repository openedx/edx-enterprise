"""
Views for the ``enterprise-user`` API endpoint.
"""

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions

from enterprise import models
from enterprise.api.v1 import serializers
from enterprise.api.v1.views.base_views import EnterpriseReadOnlyModelViewSet
from enterprise.logging import getEnterpriseLogger

LOGGER = getEnterpriseLogger(__name__)


class EnterpriseUserViewSet(EnterpriseReadOnlyModelViewSet):
    """
    API views for the ``enterprise-user`` API endpoint.
    """
    queryset = models.EnterpriseCustomerUser.objects.all()
    filter_backends = (filters.OrderingFilter, DjangoFilterBackend,)
    serializer_class = serializers.EnterpriseUserSerializer
    permission_classes = (permissions.IsAuthenticated,)

    USER_ID_FILTER = 'enterprise_customer_users__user_id'
    FILTER_FIELDS = (
        'user_id',
    )
    ORDER_FIELDS = (
        'user_id',
        'user_name',
        'enterprise_customer__contact_email'
    )

    filterset_fields = FILTER_FIELDS
    ordering_fields = ORDER_FIELDS
