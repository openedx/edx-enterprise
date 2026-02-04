"""
Views for the ``enterprise-admin-members`` API endpoint.
"""

from collections import OrderedDict

from edx_rbac.decorators import permission_required
from rest_framework import permissions, response, status
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination

from enterprise import models
from enterprise.api.v1 import serializers
from enterprise.api.v1.views.base_views import EnterpriseReadOnlyModelViewSet
from enterprise.logging import getEnterpriseLogger

LOGGER = getEnterpriseLogger(__name__)


ADMIN_MEMBER_SORT_FIELD_MAP = {
    "name": "name",
    "email": "email",
    "joined_date": "joined_date",
    "invited_date": "invited_date",
    "status": "status",
}


class EnterpriseAdminMembersPaginator(PageNumberPagination):
    """
    Paginator for enterprise admin members list responses.
    """

    page_size = 10
    page_size_query_param = "page_size"

    def get_paginated_response(self, data):
        return response.Response(
            OrderedDict(
                [
                    ("count", self.page.paginator.count),
                    ("num_pages", self.page.paginator.num_pages),
                    ("next", self.get_next_link()),
                    ("previous", self.get_previous_link()),
                    ("results", data),
                ]
            )
        )


class EnterpriseAdminMembersViewSet(EnterpriseReadOnlyModelViewSet):
    """
    API viewset for listing enterprise admin members (pending + approved).
    """

    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = serializers.EnterpriseAdminMemberSerializer
    pagination_class = EnterpriseAdminMembersPaginator

    ALLOWED_SORT_KEYS = frozenset(ADMIN_MEMBER_SORT_FIELD_MAP.keys())
    DEFAULT_SORT = "name"

    def _get_union_queryset(self, enterprise_uuid, user_query):
        """
        Return the combined pending and approved admin-member queryset.
        """
        pending_qs = (
            models.PendingEnterpriseCustomerAdminUser.objects
            .for_enterprise(enterprise_uuid, user_query)
        )

        approved_qs = (
            models.EnterpriseCustomerAdmin.objects
            .for_enterprise(enterprise_uuid, user_query)
        )

        return pending_qs.union(approved_qs)

    @permission_required(
        "enterprise.can_access_admin_dashboard",
        fn=lambda request, *args, **kwargs: kwargs.get("enterprise_uuid"),
    )
    def get_admin_members(self, request, *args, **kwargs):
        """
        GET /api/v1/{enterprise_uuid}/admins
        """
        try:
            param_serializer = serializers.EnterpriseAdminMembersRequestQuerySerializer(
                data=request.query_params
            )
            param_serializer.is_valid(raise_exception=True)

            enterprise_uuid = kwargs["enterprise_uuid"]
            user_query = param_serializer.validated_data.get("user_query") or ""
            is_reversed = param_serializer.validated_data.get("is_reversed", False)
            sort_by = param_serializer.validated_data.get("sort_by") or self.DEFAULT_SORT

            if sort_by not in self.ALLOWED_SORT_KEYS:
                sort_by = self.DEFAULT_SORT

            sort_field = f"-{sort_by}" if is_reversed else sort_by

            qs = (
                self._get_union_queryset(enterprise_uuid, user_query)
                .order_by(sort_field, "email")
            )

            page = self.paginate_queryset(qs)
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        except ValidationError as exc:
            LOGGER.exception(
                "Validation error while fetching admin members",
                extra={"enterprise_uuid": kwargs.get("enterprise_uuid")},
            )
            return response.Response(
                {"detail": exc.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )
