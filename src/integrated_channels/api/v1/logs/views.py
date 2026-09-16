"""
Viewsets for integrated_channels/v1/logs
"""
import logging
from collections import OrderedDict
from datetime import datetime

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

from django.db.models import DateTimeField
from django.db.models.functions import Cast, Coalesce, Greatest

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
    page_size_query_param = 'page_size'

    def get_paginated_response(self, data):
        return Response(OrderedDict([
            ('pages_count', self.page.paginator.num_pages),
            ('count', self.page.paginator.count),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('results', data)
        ]))


class BaseReportingSyncStatusException(exceptions.APIException):
    status_code = 400


class InvalidSortByParamException(BaseReportingSyncStatusException):
    default_detail = "Invalid sort_by filter."
    default_code = "validation_error"


class InvalidChannelCodeException(BaseReportingSyncStatusException):
    default_detail = "Invalid channel code."
    default_code = "validation_error"


def validate_sort_by_query_params(model_table, request):
    if sort_by_param := request.GET.get('sort_by'):
        expected_sort_by_filters = ["sync_status", "sync_last_attempted_at"] + \
            [field.name for field in model_table._meta.fields]
        if sort_by_param.replace("-", "") not in expected_sort_by_filters:
            raise InvalidSortByParamException


def sort_by_date_aggregation(objects, date_fields, filter, order):
    # Arbitrarily old date to make sure null dates are considered lower in the `Greatest` annotation than any existing or to be
    # created datetime in the audits
    long_ago = datetime(year=1995, month=6, day=18)
    return objects.annotate(
        newest_date=Greatest(
            *[Coalesce(field, Cast(long_ago, DateTimeField()), output_field=DateTimeField()) for field in date_fields]
        )
    ).filter(**filter).order_by(f'{order}newest_date')


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
        validate_sort_by_query_params(ContentMetadataItemTransmission, self.request)

    def get_queryset(self):
        self.validate()

        content_metadata_fields = ('enterprise_customer_uuid', 'integrated_channel_code', 'plugin_configuration_id')
        content_metadata_transmission_audit_filter = {field: self.kwargs.get(field) for field in content_metadata_fields}
        content_metadata_transmission_audit_filter['enterprise_customer_id'] = \
            content_metadata_transmission_audit_filter.pop('enterprise_customer_uuid')

        table_fields = [field.name for field in ContentMetadataItemTransmission._meta.fields]
        for query_filter in self.request.GET.keys():
            if query_filter in table_fields:
                content_metadata_transmission_audit_filter[f'{query_filter}__contains'] = self.request.GET.get(query_filter)

        # Sorting defaults to the status code field in DESC order to put failed transmission on top
        content_sort_by = ('-api_response_status_code',)
        if self.request.GET.get('sort_by'):
            # Translate the serialized `sync_status` to its DB field equivalent `api_response_status_code`
            content_sort_by = (self.request.GET.get('sort_by').replace('sync_status', 'api_response_status_code'),)

            # The serialized `sync_last_attempted_at` value is the representation of the `remote_<X>_at` values
            if "sync_last_attempted_at" in content_sort_by[0]:
                order = "-" if "-" in content_sort_by[0] else ""
                return sort_by_date_aggregation(
                    ContentMetadataItemTransmission.objects,
                    ['remote_updated_at', 'remote_deleted_at', 'remote_created_at'],
                    content_metadata_transmission_audit_filter,
                    order
                )

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
        validate_sort_by_query_params(ThisLearnerClass, self.request)

    def get_queryset(self):
        self.validate()
        integrated_channel_code = self.kwargs.get('integrated_channel_code', None)
        ThisLearnerClass = LearnerDataTransmissionAudit.get_completion_class_by_channel_code(integrated_channel_code)

        learner_data_fields = ('enterprise_customer_uuid', 'plugin_configuration_id')
        learner_data_transmission_audit_filter = {field: self.kwargs.get(field) for field in learner_data_fields}

        table_fields = [field.name for field in ThisLearnerClass._meta.fields]
        for query_filter in self.request.GET.keys():
            if query_filter in table_fields:
                learner_data_transmission_audit_filter[f'{query_filter}__contains'] = self.request.GET.get(query_filter)

        # Defaults to DESC status code to put failed transmission on top
        content_sort_by = ('-status',)
        if self.request.GET.get('sort_by'):
            # Translate the serialized `sync_status` to its DB field equivalent `api_response_status_code`
            content_sort_by = (self.request.GET.get('sort_by').replace('sync_status', 'status'),)

            # The serialized `sync_last_attempted_at` value is the representation of both the `modified` and `created` values
            if "sync_last_attempted_at" in content_sort_by[0]:
                order = "-" if "-" in content_sort_by[0] else ""
                return sort_by_date_aggregation(
                    ThisLearnerClass.objects,
                    ['modified', 'created'],
                    learner_data_transmission_audit_filter,
                    order
                )

        return ThisLearnerClass.objects.filter(**learner_data_transmission_audit_filter).order_by(*content_sort_by)
