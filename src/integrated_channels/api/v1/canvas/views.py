"""
Viewsets for integrated_channels/v1/canvas/
"""
from rest_framework import permissions, viewsets

from integrated_channels.api.v1.mixins import PermissionRequiredForIntegratedChannelMixin
from integrated_channels.canvas.models import CanvasEnterpriseCustomerConfiguration

from .serializers import CanvasEnterpriseCustomerConfigurationSerializer


class CanvasConfigurationViewSet(PermissionRequiredForIntegratedChannelMixin, viewsets.ModelViewSet):
    serializer_class = CanvasEnterpriseCustomerConfigurationSerializer
    permission_classes = (permissions.IsAuthenticated,)
    permission_required = 'enterprise.can_access_admin_dashboard'

    configuration_model = CanvasEnterpriseCustomerConfiguration
