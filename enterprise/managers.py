"""Custom queryset helpers for enterprise admin and pending-admin records."""

from django.db import models
from django.db.models import CharField, DateTimeField, F, Q, Value

from enterprise.constants import ENTERPRISE_ADMIN_ROLE


class PendingEnterpriseAdminQuerySet(models.QuerySet):
    """QuerySet helpers for pending enterprise admin users."""

    def for_enterprise(self, enterprise_uuid, user_query=None):
        """Return pending admin rows for an enterprise, optionally filtered by email."""

        qs = (
            self.filter(enterprise_customer__uuid=enterprise_uuid)
            .values("id")
            .annotate(
                email=F("user_email"),
                name=Value(None, output_field=CharField()),
                invited_date=F("created"),
                joined_date=Value(None, output_field=DateTimeField()),
                status=Value("Pending", output_field=CharField()),
            )
        )
        if user_query:
            qs = qs.filter(user_email__icontains=user_query)
        return qs


class EnterpriseAdminQuerySet(models.QuerySet):
    """QuerySet helpers for approved enterprise admin users."""

    def for_enterprise(self, enterprise_uuid, user_query=None):
        """Return approved admin rows for an enterprise, optionally filtered by username/email."""

        admin_role_lookup = (
            "enterprise_customer_user__user_fk__"
            "systemwideenterpriseuserroleassignment__role__name"
        )

        qs = (
            self.filter(
                enterprise_customer_user__enterprise_customer__uuid=enterprise_uuid,
                enterprise_customer_user__user_fk__is_active=True,
                **{admin_role_lookup: ENTERPRISE_ADMIN_ROLE},
            )
            .annotate(
                email=F("enterprise_customer_user__user_fk__email"),
                name=F("enterprise_customer_user__user_fk__username"),
                invited_date=Value(None, output_field=DateTimeField()),
                joined_date=F("created"),
                status=Value("Admin", output_field=CharField()),
            )
            .values(
                "enterprise_customer_user_id",
                "email",
                "name",
                "invited_date",
                "joined_date",
                "status",
            )
        )

        if user_query:
            qs = qs.filter(
                Q(enterprise_customer_user__user_fk__username__icontains=user_query)
                | Q(enterprise_customer_user__user_fk__email__icontains=user_query)
            )
        return qs
