"""
Viewsets for integrated_channels/v1/moodle/
"""
from rest_framework import exceptions, permissions, status, viewsets

from integrated_channels.api.v1.mixins import PermissionRequiredForIntegratedChannelMixin
from integrated_channels.moodle.models import MoodleEnterpriseCustomerConfiguration

from .serializers import MoodleConfigSerializer


class MoodleConfigurationViewSet(PermissionRequiredForIntegratedChannelMixin, viewsets.ModelViewSet):
    serializer_class = MoodleConfigSerializer
    permission_classes = (permissions.IsAuthenticated,)
    permission_required = 'enterprise.can_access_admin_dashboard'

    configuration_model = MoodleEnterpriseCustomerConfiguration
