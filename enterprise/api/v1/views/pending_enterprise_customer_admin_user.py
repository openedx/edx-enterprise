"""
Views for the ``pending-enterprise-customer-admin-user`` API endpoint.
"""

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions

from enterprise import models
from enterprise.api.v1 import serializers
from enterprise.api.v1.permissions import IsProvisioningAdmin
from enterprise.api.v1.views.base_views import EnterpriseReadWriteModelViewSet
from enterprise.logging import getEnterpriseLogger

LOGGER = getEnterpriseLogger(__name__)


class PendingEnterpriseCustomerAdminUserViewSet(EnterpriseReadWriteModelViewSet):
    """
    API views for the ``pending-enterprise-customer-admin-user`` API endpoint.
    Requires staff permissions
    """
    queryset = models.PendingEnterpriseCustomerAdminUser.objects.all()
    filter_backends = (filters.OrderingFilter, DjangoFilterBackend)
    serializer_class = serializers.PendingEnterpriseCustomerAdminUserSerializer
    permission_classes = (permissions.IsAuthenticated, IsProvisioningAdmin)

    FIELDS = (
        'enterprise_customer', 'user_email',
    )
    filterset_fields = FIELDS
    ordering_fields = FIELDS
