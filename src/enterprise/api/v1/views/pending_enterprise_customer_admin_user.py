"""
Views for the ``pending-enterprise-customer-admin-user`` API endpoint.
"""

from django_filters.rest_framework import DjangoFilterBackend
from edx_rbac.mixins import PermissionRequiredMixin
from rest_framework import filters, permissions

from enterprise import models
from enterprise.api.v1 import serializers
from enterprise.api.v1.views.base_views import EnterpriseReadWriteModelViewSet
from enterprise.constants import PENDING_ENT_CUSTOMER_ADMIN_PROVISIONING_ADMIN_ACCESS_PERMISSION
from enterprise.logging import getEnterpriseLogger

LOGGER = getEnterpriseLogger(__name__)


class PendingEnterpriseCustomerAdminUserViewSet(PermissionRequiredMixin, EnterpriseReadWriteModelViewSet):
    """
    API views for the ``pending-enterprise-customer-admin-user`` API endpoint.
    Requires staff permissions
    """
    queryset = models.PendingEnterpriseCustomerAdminUser.objects.all()
    filter_backends = (filters.OrderingFilter, DjangoFilterBackend)
    serializer_class = serializers.PendingEnterpriseCustomerAdminUserSerializer
    permission_classes = (permissions.IsAuthenticated,)
    permission_required = PENDING_ENT_CUSTOMER_ADMIN_PROVISIONING_ADMIN_ACCESS_PERMISSION

    FIELDS = (
        'enterprise_customer', 'user_email',
    )
    filterset_fields = FIELDS
    ordering_fields = FIELDS
