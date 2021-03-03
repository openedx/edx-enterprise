"""
Viewsets for integrated_channels/v1/degreed/
"""
from rest_framework import exceptions, permissions, status, viewsets

from integrated_channels.api.v1.mixins import PermissionRequiredForIntegratedChannelMixin
from integrated_channels.degreed.models import DegreedEnterpriseCustomerConfiguration

from .serializers import DegreedConfigSerializer


class DegreedConfigurationViewSet(PermissionRequiredForIntegratedChannelMixin, viewsets.ModelViewSet):
    serializer_class = DegreedConfigSerializer
    permission_classes = (permissions.IsAuthenticated,)
    permission_required = 'enterprise.can_access_admin_dashboard'

    configuration_model = DegreedEnterpriseCustomerConfiguration
