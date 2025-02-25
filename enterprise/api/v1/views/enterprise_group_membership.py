"""
Views for the ``enterprise-group-membership`` API endpoint.
"""

from django_filters.rest_framework import DjangoFilterBackend
from edx_rbac.decorators import permission_required
from rest_framework import filters, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.status import (
    HTTP_400_BAD_REQUEST,
)

from django.contrib import auth
from django.db.models import Q
from django.http import Http404

from enterprise import constants, models, rules, utils
from enterprise.api.utils import get_enterprise_customer_from_enterprise_group_id
from enterprise.api.v1 import serializers
from enterprise.api.v1.views.base_views import EnterpriseReadWriteModelViewSet
from enterprise.logging import getEnterpriseLogger
from enterprise.tasks import send_group_membership_invitation_notification, send_group_membership_removal_notification
from enterprise.utils import localized_utcnow

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
    def get_memberships(self, request):
        """
        Endpoint that filters by `lms_user_id` and `enterprise_uuid`.

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

        if lms_user_id:
            queryset = queryset.filter(enterprise_customer_user__user_id=lms_user_id)
        if enterprise_uuid:
            queryset = queryset.filter(enterprise_customer_user__enterprise_customer__uuid=enterprise_uuid)

        page = self.paginate_queryset(queryset)

        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)
