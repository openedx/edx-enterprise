"""
Viewsets for integrated_channels/v1/blackboard/
"""
from rest_framework import exceptions, permissions, status, viewsets

from integrated_channels.api.v1.mixins import PermissionRequiredForIntegratedChannelMixin
from integrated_channels.blackboard.models import BlackboardEnterpriseCustomerConfiguration

from .serializers import BlackboardConfigSerializer


class BlackboardConfigurationViewSet(PermissionRequiredForIntegratedChannelMixin, viewsets.ModelViewSet):
    serializer_class = BlackboardConfigSerializer
    permission_classes = (permissions.IsAuthenticated,)
    permission_required = 'enterprise.can_access_admin_dashboard'

    configuration_model = BlackboardEnterpriseCustomerConfiguration
