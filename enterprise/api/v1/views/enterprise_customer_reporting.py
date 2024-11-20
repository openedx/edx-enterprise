"""
Views for the Enterprise Customer Reporting API.
"""

from edx_rbac.decorators import permission_required
from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from rest_framework import permissions, status
from rest_framework.authentication import SessionAuthentication
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_404_NOT_FOUND
from rest_framework.views import APIView

from enterprise import models
from enterprise.api.utils import get_ent_cust_from_report_config_uuid, get_enterprise_customer_from_user_id
from enterprise.api.v1 import serializers
from enterprise.api.v1.views.base_views import EnterpriseReadWriteModelViewSet
from enterprise.utils import get_enterprise_customer


class EnterpriseCustomerReportingConfigurationViewSet(EnterpriseReadWriteModelViewSet):
    """
    API views for the ``enterprise-customer-reporting`` API endpoint.
    """

    queryset = models.EnterpriseCustomerReportingConfiguration.objects.all()
    serializer_class = serializers.EnterpriseCustomerReportingConfigurationSerializer
    lookup_field = 'uuid'
    permission_classes = [permissions.IsAuthenticated]

    USER_ID_FILTER = 'enterprise_customer__enterprise_customer_users__user_id'
    FIELDS = (
        'enterprise_customer',
    )
    filterset_fields = FIELDS
    ordering_fields = FIELDS

    @permission_required(
        'enterprise.can_manage_reporting_config',
        fn=lambda request, *args, **kwargs: get_ent_cust_from_report_config_uuid(kwargs['uuid']))
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @permission_required(
        'enterprise.can_manage_reporting_config',
        fn=lambda request, *args, **kwargs: get_enterprise_customer_from_user_id(request.user.id))
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @permission_required(
        'enterprise.can_manage_reporting_config',
        fn=lambda request, *args, **kwargs: request.data.get('enterprise_customer_id'))
    def create(self, request, *args, **kwargs):
        config_data = request.data.copy()
        serializer = self.get_serializer(data=config_data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @permission_required(
        'enterprise.can_manage_reporting_config',
        fn=lambda request, *args, **kwargs: get_ent_cust_from_report_config_uuid(kwargs['uuid']))
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @permission_required(
        'enterprise.can_manage_reporting_config',
        fn=lambda request, *args, **kwargs: get_ent_cust_from_report_config_uuid(kwargs['uuid']))
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @permission_required(
        'enterprise.can_manage_reporting_config',
        fn=lambda request, *args, **kwargs: get_ent_cust_from_report_config_uuid(kwargs['uuid']))
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)


class EnterpriseCustomerReportTypesView(APIView):
    """
    API for getting the report types associated with an enterprise customer
    """
    authentication_classes = [JwtAuthentication, SessionAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get']

    @staticmethod
    def _get_data_types_with_recent_progress_type(data_types):
        """
        Get the data types with only the most recent 'progress' type version

        Arguments:
            data_types (list<str, str>): List of data type tuples.

        Returns:
            (list<str, str>): List of data type tuples with only the most recent 'progress' type.
            e.g. [ ... ('progress', 'progress_v3')]
        """
        progress_data_types = [data_type for data_type in data_types if data_type[1].startswith('progress')]
        progress_data_types.sort(key=lambda data_type: data_type[1])
        data_types_for_frontend = [data_type for data_type in data_types if not data_type[1].startswith('progress')]
        data_types_for_frontend.append((progress_data_types[-1][1], 'progress'))
        return data_types_for_frontend

    @staticmethod
    def _get_data_types_for_non_pearson_customers(data_types):
        """
        Get the data types for non-pearson customers

        Arguments:
            data_types (list<str, str>): List of data type tuples.

        Returns:
            (list<str, str>): List of data type tuples without the Pearson specific types.
        """
        reduced_data_types = []
        for data_type in data_types:
            if data_type[1] not in models.EnterpriseCustomerReportingConfiguration.MANUAL_REPORTS:
                reduced_data_types.append(data_type)
        return reduced_data_types

    @permission_required(
        'enterprise.can_access_admin_dashboard',
        fn=lambda request, enterprise_uuid: enterprise_uuid
    )
    def get(self, request, enterprise_uuid):
        """
        Get the dropdown choices for EnterpriseCustomerReportingConfiguration
        """
        enterprise_customer = get_enterprise_customer(enterprise_uuid)
        if not enterprise_customer:
            return Response({'detail': 'Could not find the enterprise customer.'}, status=HTTP_404_NOT_FOUND)

        meta = models.EnterpriseCustomerReportingConfiguration._meta
        choices = {}
        for field in meta.get_fields():
            if hasattr(field, 'choices') and field.choices:
                choices[field.name] = field.choices
        # filter out deprecated 'progress' type report versions
        data_types_for_frontend = self._get_data_types_with_recent_progress_type(list(choices.get('data_type', [])))
        # remove Pearson only reports
        choices['data_type'] = (
            self._get_data_types_for_non_pearson_customers(data_types_for_frontend)
            if 'pearson' not in enterprise_customer.slug
            else data_types_for_frontend
        )

        return Response(data=choices, status=HTTP_200_OK)
