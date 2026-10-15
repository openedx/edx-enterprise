"""
Views for the ``enterprise-admin-members`` API endpoint.
"""

from edx_rbac.decorators import permission_required
from rest_framework import filters, mixins, permissions, viewsets
from rest_framework.pagination import PageNumberPagination

from django.db.models import CharField, F, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce, NullIf

from enterprise import models
from enterprise.api.v1 import serializers
from enterprise.api.v1.views.base_views import EnterpriseViewSet
from enterprise.constants import ENTERPRISE_ADMIN_ROLE
from enterprise.logging import getEnterpriseLogger

try:
    from common.djangoapps.student.models import UserProfile
except ImportError:
    UserProfile = None

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
    # Add email as secondary sort to ensure deterministic ordering when multiple
    # records share the same name (e.g., pending admins with blank names).
    ordering = ["name", "email"]

    @classmethod
    def _get_active_admins_qs(cls, enterprise_uuid):
        """
        Return annotated ValuesQuerySet of active (joined) admins.

        Clears default model ordering to allow safe use with ``.union()``.

        Resolves ``name`` from ``auth_userprofile.name`` when available
        (the canonical full-name field in edX). Falls back to
        ``first_name`` and finally ``username`` so the column is always
        populated.
        """
        # Build name expression: prefer auth_userprofile.name (where edX
        # stores user full names), fall back to auth_user.first_name, then
        # username. UserProfile may be unavailable outside edx-platform
        # (e.g. unit tests), in which case we drop the profile lookup.
        name_args = []
        if UserProfile is not None:  # pragma: no cover
            profile_name_subquery = UserProfile.objects.filter(
                user_id=OuterRef("enterprise_customer_user__user_fk__id"),
            ).values("name")[:1]
            name_args.append(NullIf(Subquery(profile_name_subquery), Value("")))
        name_args.extend([
            NullIf(F("enterprise_customer_user__user_fk__first_name"), Value("")),
            F("enterprise_customer_user__user_fk__username"),
        ])

        return (
            models.EnterpriseCustomerAdmin.objects.filter(
                enterprise_customer_user__enterprise_customer__uuid=enterprise_uuid,
                enterprise_customer_user__active=True,
                enterprise_customer_user__user_fk__systemwideenterpriseuserroleassignment__role__name=(
                    ENTERPRISE_ADMIN_ROLE
                ),
                enterprise_customer_user__user_fk__systemwideenterpriseuserroleassignment__enterprise_customer__uuid=(
                    enterprise_uuid
                ),
            )
            .annotate(
                admin_id=F("enterprise_customer_user__id"),
                name=Coalesce(*name_args, output_field=CharField()),
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

        Pending admins do not yet have an ``EnterpriseCustomerUser`` link,
        so we resolve ``name`` by matching ``user_email`` against any
        existing ``auth_userprofile`` row. When no profile exists (or the
        UserProfile model is unavailable), ``name`` is blank.
        """
        if UserProfile is not None:  # pragma: no cover
            profile_name_subquery = UserProfile.objects.filter(
                user__email=OuterRef("user_email"),
            ).values("name")[:1]
            name_expression = Coalesce(
                NullIf(Subquery(profile_name_subquery), Value("")),
                Value(""),
                output_field=CharField(),
            )
        else:
            name_expression = Value("", output_field=CharField())

        return (
            models.PendingEnterpriseCustomerAdminUser.objects.filter(
                enterprise_customer__uuid=enterprise_uuid,
            )
            .annotate(
                admin_id=F("id"),
                name=name_expression,
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
