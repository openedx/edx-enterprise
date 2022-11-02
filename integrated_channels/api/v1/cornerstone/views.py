"""
Viewsets for integrated_channels/v1/cornerstone/
"""
from rest_framework import permissions, viewsets

from integrated_channels.api.v1.mixins import PermissionRequiredForIntegratedChannelMixin
from integrated_channels.cornerstone.models import CornerstoneEnterpriseCustomerConfiguration

from .serializers import CornerstoneConfigSerializer


class CornerstoneConfigurationViewSet(PermissionRequiredForIntegratedChannelMixin, viewsets.ModelViewSet):
    serializer_class = CornerstoneConfigSerializer
    permission_classes = (permissions.IsAuthenticated,)
    permission_required = 'enterprise.can_access_admin_dashboard'

    configuration_model = CornerstoneEnterpriseCustomerConfiguration
