"""
Viewsets related to the integrated_channels Degreed2 model
"""
from rest_framework import exceptions, permissions, status, viewsets

from integrated_channels.api.v1.mixins import PermissionRequiredForIntegratedChannelMixin
from integrated_channels.degreed2.models import Degreed2EnterpriseCustomerConfiguration

from .serializers import Degreed2ConfigSerializer


class Degreed2ConfigurationViewSet(PermissionRequiredForIntegratedChannelMixin, viewsets.ModelViewSet):
    serializer_class = Degreed2ConfigSerializer
    permission_classes = (permissions.IsAuthenticated,)
    permission_required = 'enterprise.can_access_admin_dashboard'

    configuration_model = Degreed2EnterpriseCustomerConfiguration
