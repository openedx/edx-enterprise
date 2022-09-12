"""
Viewsets for integrated_channels/v1/logs
"""
import logging
from rest_framework import exceptions, permissions, status, viewsets, mixins
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
from rest_framework.pagination import PageNumberPagination

from integrated_channels.api.v1.mixins import PermissionRequiredForIntegratedChannelMixin
from integrated_channels.integrated_channel.models import (
    ContentMetadataItemTransmission,
    LearnerDataTransmissionAudit,
)

from .serializers import (
    ContentSyncStatusSerializer,
    LearnerSyncStatusSerializer,
    GenericLearnerSyncStatusSerializer,
)

LOGGER = logging.getLogger(__name__)


class ContentSyncStatusViewSet(PermissionRequiredForIntegratedChannelMixin, viewsets.ModelViewSet):
    serializer_class = ContentSyncStatusSerializer
    permission_classes = (permissions.IsAuthenticated,)
    permission_required = 'enterprise.can_access_admin_dashboard'
    pagination_class = PageNumberPagination

    def get_queryset(self):
        enterprise_customer_uuid = self.kwargs.get('enterprise_customer_uuid', None)
        integrated_channel_code = self.kwargs.get('integrated_channel_code', None)
        plugin_configuration_id = self.kwargs.get('plugin_configuration_id', None)
        return ContentMetadataItemTransmission.objects.filter(
            enterprise_customer_id=enterprise_customer_uuid,
            integrated_channel_code=integrated_channel_code,
            plugin_configuration_id=plugin_configuration_id
        )

class LearnerSyncStatusViewSet(PermissionRequiredForIntegratedChannelMixin, viewsets.ModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    permission_required = 'enterprise.can_access_admin_dashboard'
    pagination_class = PageNumberPagination

    def get_serializer_class(self):
        integrated_channel_code = self.kwargs.get('integrated_channel_code', None)
        return LearnerSyncStatusSerializer.get_class_by_channel_code(integrated_channel_code)

    def get_queryset(self):
        enterprise_customer_uuid = self.kwargs.get('enterprise_customer_uuid', None)
        integrated_channel_code = self.kwargs.get('integrated_channel_code', None)
        plugin_configuration_id = self.kwargs.get('plugin_configuration_id', None)
        ThisLearnerClass = LearnerDataTransmissionAudit.get_class_by_channel_code(integrated_channel_code)
        LOGGER.info(f'learner data class: {ThisLearnerClass}')

        return ThisLearnerClass.objects.filter(
            enterprise_customer_uuid=enterprise_customer_uuid,
            plugin_configuration_id=plugin_configuration_id
        )
