"""
Views for the ``pending-enterprise-customer-admin-user`` API endpoint.
"""

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions

from enterprise import models
from enterprise.api.v1 import serializers
from enterprise.api.v1.permissions import IsInProvisioningAdminGroup
from enterprise.api.v1.views.base_views import EnterpriseReadWriteModelViewSet
from enterprise.logging import getEnterpriseLogger

LOGGER = getEnterpriseLogger(__name__)


class EnterpriseUserViewSet(EnterpriseReadWriteModelViewSet):
    """
    API views for the ``enterprise-user`` API endpoint.
    """
    queryset = models.PendingEnterpriseCustomerAdminUser.objects.all()
    filter_backends = (filters.OrderingFilter, DjangoFilterBackend,)
    serializer_class = serializers.EnterpriseUserSerializer
    permission_classes = (permissions.IsAuthenticated,)

    USER_ID_FILTER = 'enterprise_customer_users__user_id'
    FIELDS = (
        'enterprise_customer_user_id', 'user_name', 'user_email', 'is_admin',
        'pending_enterprise_customer_user_id', 'is_pending_admin'
    )
    filterset_fields = FIELDS
    ordering_fields = FIELDS
