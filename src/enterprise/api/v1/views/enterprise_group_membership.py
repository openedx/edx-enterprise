"""
Views for the ``enterprise-group-membership`` API endpoint.
"""

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.status import HTTP_400_BAD_REQUEST

from django.contrib import auth

from enterprise import models
from enterprise.api.v1 import serializers
from enterprise.api.v1.views.base_views import EnterpriseReadWriteModelViewSet
from enterprise.constants import GROUP_TYPE_FLEX
from enterprise.logging import getEnterpriseLogger

LOGGER = getEnterpriseLogger(__name__)

User = auth.get_user_model()


class EnterpriseGroupMembershipViewSet(EnterpriseReadWriteModelViewSet):
    """
    API views for the ``enterprise-group-membership`` API endpoint.
    """
    queryset = models.EnterpriseGroupMembership.all_objects.all()
    permission_classes = (permissions.IsAuthenticated,)
    filter_backends = (filters.OrderingFilter, DjangoFilterBackend,)
    serializer_class = serializers.EnterpriseGroupMembershipSerializer

    @action(detail=False, methods=['get'])
    def get_flex_group_memberships(self, request):
        """
        Endpoint that filters flex group memberships by `lms_user_id` and `enterprise_uuid`.

        Parameters:
        - `lms_user_id` (str): Filter results by the LMS user ID.
        - `enterprise_uuid` (str): Filter results by the Enterprise UUID.

        Response:
        - Returns a list of EnterpriseGroupMemberships matching the filters.
        - Response format: JSON array of serialized `EnterpriseGroupMembership` objects.
        """
        queryset = self.queryset

        lms_user_id = request.query_params.get('lms_user_id')
        enterprise_uuid = request.query_params.get('enterprise_uuid')

        if not lms_user_id or not enterprise_uuid:
            return Response(
                {"error": "Both 'lms_user_id' and 'enterprise_uuid' are required parameters."},
                status=HTTP_400_BAD_REQUEST
            )

        queryset = self.queryset.filter(
            enterprise_customer_user__user_id=lms_user_id,
            enterprise_customer_user__enterprise_customer__uuid=enterprise_uuid,
            group__group_type=GROUP_TYPE_FLEX
        )
        page = self.paginate_queryset(queryset)

        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)
