"""
Views for the ``enterprise-admin-members`` API endpoint.
"""

from edx_rbac.decorators import permission_required
from rest_framework import filters, mixins, permissions, viewsets
from rest_framework.pagination import PageNumberPagination

from django.db.models import CharField, F, Value
from django.db.models.functions import Coalesce

from enterprise import models
from enterprise.api.v1 import serializers
from enterprise.api.v1.views.base_views import EnterpriseViewSet
from enterprise.logging import getEnterpriseLogger

LOGGER = getEnterpriseLogger(__name__)


class EnterpriseAdminMembersPagination(PageNumberPagination):
    """
    Pagination class for the enterprise admin members endpoint.
    """

    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class EnterpriseAdminMembersViewSet(
    EnterpriseViewSet,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """
    API for listing enterprise admin members (both active and pending).

    GET /{enterprise_uuid}/admins

    Returns a paginated list of enterprise administrators with status:
      - ``Admin`` -- Active admin (joined)
      - ``Pending`` -- Admin invited but not yet joined

    Query parameters:
      - ``user_query`` -- Filter by name or email (case-insensitive contains)
      - ``ordering`` -- One of: name, email, joined_date, invited_date, status
                        Prefix with ``-`` for descending (e.g. ``-name``)
    """

    serializer_class = serializers.EnterpriseAdminMemberSerializer
    permission_classes = (permissions.IsAuthenticated,)
    pagination_class = EnterpriseAdminMembersPagination
    filter_backends = (filters.OrderingFilter,)

    # DRF OrderingFilter settings
    ordering_fields = ["name", "email", "joined_date", "invited_date", "status"]
    ordering = ["name"]

    @classmethod
    def _get_active_admins_qs(cls, enterprise_uuid):
        """
        Return annotated ValuesQuerySet of active (joined) admins.

        Clears default model ordering to allow safe use with ``.union()``.
        """
        return (
            models.EnterpriseCustomerAdmin.objects.filter(
                enterprise_customer_user__enterprise_customer__uuid=enterprise_uuid,
                enterprise_customer_user__user_fk__is_active=True,
            )
            .annotate(
                admin_id=F("enterprise_customer_user__id"),
                name=Coalesce(
                    "enterprise_customer_user__user_fk__first_name",
                    "enterprise_customer_user__user_fk__username",
                    output_field=CharField(),
                ),
                email=F("enterprise_customer_user__user_fk__email"),
                invited_date=Value(None, output_field=CharField()),
                joined_date=F("created"),
                status=Value("Admin", output_field=CharField()),
            )
            .order_by()
            .values(
                "admin_id",
                "name",
                "email",
                "invited_date",
                "joined_date",
                "status",
            )
        )

    @classmethod
    def _get_pending_admins_qs(cls, enterprise_uuid):
        """
        Return annotated ValuesQuerySet of pending (invited) admins.

        Clears default model ordering to allow safe use with ``.union()``.
        """
        return (
            models.PendingEnterpriseCustomerAdminUser.objects.filter(
                enterprise_customer__uuid=enterprise_uuid,
            )
            .annotate(
                admin_id=F("id"),
                name=Value(None, output_field=CharField()),
                email=F("user_email"),
                invited_date=F("created"),
                joined_date=Value(None, output_field=CharField()),
                status=Value("Pending", output_field=CharField()),
            )
            .order_by()
            .values(
                "admin_id",
                "name",
                "email",
                "invited_date",
                "joined_date",
                "status",
            )
        )

    @permission_required(
        "enterprise.can_access_admin_dashboard",
        fn=lambda request, *args, **kwargs: kwargs.get("enterprise_uuid"),
    )
    def list(self, request, *args, **kwargs):
        """
        List enterprise admin members with DRF-native ordering and pagination.
        """
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        """
        Build a union queryset of active + pending admins, scoped to the
        requested enterprise. Applies ``user_query`` search filtering
        *before* the union (since union querysets do not support ``.filter()``).
        """
        enterprise_uuid = self.kwargs.get("enterprise_uuid")
        user_query = self.request.query_params.get("user_query", "").strip()

        active_qs = self._get_active_admins_qs(enterprise_uuid)
        pending_qs = self._get_pending_admins_qs(enterprise_uuid)

        if user_query:
            active_qs = active_qs.filter(name__icontains=user_query) | active_qs.filter(
                email__icontains=user_query
            )
            pending_qs = pending_qs.filter(email__icontains=user_query)

        return active_qs.union(pending_qs)
