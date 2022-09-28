"""
Viewsets for integrated_channels/v1/logs
"""
import logging

from rest_framework import exceptions, mixins, permissions, status, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_202_ACCEPTED,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
    HTTP_422_UNPROCESSABLE_ENTITY,
    HTTP_500_INTERNAL_SERVER_ERROR,
)

from integrated_channels.api.v1.mixins import PermissionRequiredForIntegratedChannelMixin
from integrated_channels.integrated_channel.models import (
    ContentMetadataItemTransmission,
    EnterpriseCustomerPluginConfiguration,
    LearnerDataTransmissionAudit,
)

from .serializers import ContentSyncStatusSerializer, GenericLearnerSyncStatusSerializer, LearnerSyncStatusSerializer

LOGGER = logging.getLogger(__name__)


class ContentSyncStatusViewSet(PermissionRequiredForIntegratedChannelMixin, viewsets.ModelViewSet):
    """
    Sync-status APIs for `ContentMetadataItemTransmission` items.
    """
    serializer_class = ContentSyncStatusSerializer
    permission_classes = (permissions.IsAuthenticated,)
    permission_required = 'enterprise.can_access_admin_dashboard'
    pagination_class = PageNumberPagination

    def get_queryset(self):
        enterprise_customer_uuid = self.kwargs.get('enterprise_customer_uuid', None)
        integrated_channel_code = self.kwargs.get('integrated_channel_code', None)
        plugin_configuration_id = self.kwargs.get('plugin_configuration_id', None)
        channel_config_cls = EnterpriseCustomerPluginConfiguration.get_class_by_channel_code(integrated_channel_code)
        if channel_config_cls is None:
            raise exceptions.ParseError("Invalid channel code.")
        return ContentMetadataItemTransmission.objects.filter(
            enterprise_customer_id=enterprise_customer_uuid,
            integrated_channel_code=integrated_channel_code,
            plugin_configuration_id=plugin_configuration_id
        )


class LearnerSyncStatusViewSet(PermissionRequiredForIntegratedChannelMixin, viewsets.ModelViewSet):
    """
    Sync-status APIs for `LearnerDataTransmissionAudit` implementation items.
    """
    permission_classes = (permissions.IsAuthenticated,)
    permission_required = 'enterprise.can_access_admin_dashboard'
    pagination_class = PageNumberPagination

    def get_serializer_class(self):
        integrated_channel_code = self.kwargs.get('integrated_channel_code', None)
        serializer = LearnerSyncStatusSerializer.get_class_by_channel_code(integrated_channel_code)
        if serializer is None:
            raise exceptions.ParseError("Invalid channel code.")
        return serializer

    def get_queryset(self):
        enterprise_customer_uuid = self.kwargs.get('enterprise_customer_uuid', None)
        integrated_channel_code = self.kwargs.get('integrated_channel_code', None)
        plugin_configuration_id = self.kwargs.get('plugin_configuration_id', None)
        ThisLearnerClass = LearnerDataTransmissionAudit.get_class_by_channel_code(integrated_channel_code)
        if ThisLearnerClass is None:
            raise exceptions.ParseError("Invalid channel code.")

        return ThisLearnerClass.objects.filter(
            enterprise_customer_uuid=enterprise_customer_uuid,
            plugin_configuration_id=plugin_configuration_id
        )
