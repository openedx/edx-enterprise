"""
Viewsets for integrated_channels/v1/sap_success_factors/
"""
from rest_framework import exceptions, permissions, status, viewsets

from integrated_channels.api.v1.mixins import PermissionRequiredForIntegratedChannelMixin
from integrated_channels.sap_success_factors.models import SAPSuccessFactorsEnterpriseCustomerConfiguration

from .serializers import SAPSuccessFactorsConfigSerializer


class SAPSuccessFactorsConfigurationViewSet(PermissionRequiredForIntegratedChannelMixin, viewsets.ModelViewSet):
    serializer_class = SAPSuccessFactorsConfigSerializer
    permission_classes = (permissions.IsAuthenticated,)
    permission_required = 'enterprise.can_access_admin_dashboard'

    configuration_model = SAPSuccessFactorsEnterpriseCustomerConfiguration
