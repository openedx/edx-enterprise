"""
Viewsets for integrated_channels/v1/logs
"""
from collections import OrderedDict
import logging

from django.db.models import Q
from rest_framework import exceptions, permissions, viewsets
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

from .serializers import ContentSyncStatusSerializer, LearnerSyncStatusSerializer

LOGGER = logging.getLogger(__name__)


class ReportingSyncStatusPagination(PageNumberPagination):
    page_size = 10

    def get_paginated_response(self, data):
        return Response(OrderedDict([
            ('pages_count', self.page.paginator.num_pages),
            ('count', self.page.paginator.count),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('results', data)
        ]))


class InvalidSortByParamException(exceptions.APIException):
    status_code = 400
    default_detail = "Invalid sort_by filter."
    default_code = "validation_error"


class InvalidChannelCodeException(exceptions.APIException):
    status_code = 400
    default_detail = "Invalid channel code."
    default_code = "validation_error"


class ContentSyncStatusViewSet(PermissionRequiredForIntegratedChannelMixin, viewsets.ModelViewSet):
    """
    Sync-status APIs for `ContentMetadataItemTransmission` items.
    """
    serializer_class = ContentSyncStatusSerializer
    permission_classes = (permissions.IsAuthenticated,)
    permission_required = 'enterprise.can_access_admin_dashboard'
    pagination_class = ReportingSyncStatusPagination

    def validate(self):
        integrated_channel_code = self.kwargs.get('integrated_channel_code')
        channel_config_cls = EnterpriseCustomerPluginConfiguration.get_class_by_channel_code(integrated_channel_code)
        if channel_config_cls is None:
            raise InvalidChannelCodeException

        if sort_by_param := self.request.GET.get('sort_by'):
            if sort_by_param.replace("-", "") not in ["sync_status", "sync_last_attempted_at"]:
                if sort_by_param.replace("-", "") not in [field.name for field in ContentMetadataItemTransmission._meta.fields]:
                    raise InvalidSortByParamException

    def get_queryset(self):
        self.validate()
        content_metadata_transmission_audit_filter = {
            "enterprise_customer_id": self.kwargs.get('enterprise_customer_uuid'),
            "integrated_channel_code": self.kwargs.get('integrated_channel_code'),
            "plugin_configuration_id": self.kwargs.get('plugin_configuration_id'),
        }

        if self.request.GET.get('content_title'):
            content_metadata_transmission_audit_filter['content_title__contains'] = self.request.GET.get('content_title')
        if self.request.GET.get('content_id'):
            content_metadata_transmission_audit_filter['content_id__contains'] = self.request.GET.get('content_id')

        # Sorting defaults to the status code field in DESC order to put failed transmission on top
        content_sort_by = ('-api_response_status_code',)
        if self.request.GET.get('sort_by'):
            # Translate the serialized `sync_status` to its DB field equivelant `api_response_status_code`
            content_sort_by = (self.request.GET.get('sort_by').replace('sync_status', 'api_response_status_code'),)

            # The serialized `sync_last_attempted_at` value is the representation of the `remote_<X>_at` values
            if "sync_last_attempted_at" in content_sort_by[0]:
                order = "-" if "-" in content_sort_by[0] else ""
                content_sort_by = (f"{order}remote_deleted_at", f"{order}remote_updated_at", f"{order}remote_created_at")

        return ContentMetadataItemTransmission.objects.filter(
            **content_metadata_transmission_audit_filter
        ).order_by(*content_sort_by)


class LearnerSyncStatusViewSet(PermissionRequiredForIntegratedChannelMixin, viewsets.ModelViewSet):
    """
    Sync-status APIs for `LearnerDataTransmissionAudit` implementation items.
    """
    permission_classes = (permissions.IsAuthenticated,)
    permission_required = 'enterprise.can_access_admin_dashboard'
    pagination_class = ReportingSyncStatusPagination

    def get_serializer_class(self):
        integrated_channel_code = self.kwargs.get('integrated_channel_code', None)
        serializer = LearnerSyncStatusSerializer.get_completion_class_by_channel_code(integrated_channel_code)
        if serializer is None:
            raise exceptions.ParseError("Invalid channel code.")
        return serializer

    def validate(self):
        integrated_channel_code = self.kwargs.get('integrated_channel_code', None)
        ThisLearnerClass = LearnerDataTransmissionAudit.get_completion_class_by_channel_code(integrated_channel_code)
        if ThisLearnerClass is None:
            raise InvalidChannelCodeException

        if sort_by_param := self.request.GET.get('sort_by'):
            if sort_by_param.replace("-", "") not in ["sync_status", "sync_last_attempted_at"]:
                if sort_by_param.replace("-", "") not in [field.name for field in ThisLearnerClass._meta.fields]:
                    raise InvalidSortByParamException

    def get_queryset(self):
        self.validate()
        enterprise_customer_uuid = self.kwargs.get('enterprise_customer_uuid', None)
        integrated_channel_code = self.kwargs.get('integrated_channel_code', None)
        plugin_configuration_id = self.kwargs.get('plugin_configuration_id', None)
        ThisLearnerClass = LearnerDataTransmissionAudit.get_completion_class_by_channel_code(integrated_channel_code)

        learner_data_transmission_audit_filter = {
            "enterprise_customer_uuid": enterprise_customer_uuid,
            "plugin_configuration_id": plugin_configuration_id,
        }

        if self.request.GET.get('user_email'):
            learner_data_transmission_audit_filter['user_email__contains'] = self.request.GET.get('user_email')
        if self.request.GET.get('content_title'):
            learner_data_transmission_audit_filter['content_title__contains'] = self.request.GET.get('content_title')

        # Defaults to DESC status code to put failed transmission on top
        content_sort_by = ('-status',)
        if self.request.GET.get('sort_by'):
            # Translate the serialized `sync_status` to its DB field equivelant `api_response_status_code`
            content_sort_by = (self.request.GET.get('sort_by').replace('sync_status', 'status'),)

            # The serialized `sync_last_attempted_at` value is the representation of both the `modified` and `created` values
            if "sync_last_attempted_at" in content_sort_by[0]:
                order = "-" if "-" in content_sort_by[0] else ""
                content_sort_by = (f"{order}modified", f"{order}created")

        return ThisLearnerClass.objects.filter(**learner_data_transmission_audit_filter).order_by(*content_sort_by)
