"""
Views for the ``enterprise-user`` API endpoint.
"""

from collections import OrderedDict

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, response, status
from rest_framework.pagination import PageNumberPagination

from django.contrib import auth
from django.core.exceptions import ValidationError
from django.db.models import Case, CharField, F, Q, When

from enterprise import models
from enterprise.api.v1 import serializers
from enterprise.api.v1.views.base_views import EnterpriseReadOnlyModelViewSet
from enterprise.logging import getEnterpriseLogger

User = auth.get_user_model()

LOGGER = getEnterpriseLogger(__name__)


class EnterpriseCustomerSupportPaginator(PageNumberPagination):
    """Custom paginator for the enterprise customer support."""

    page_size = 8

    def get_paginated_response(self, data):
        """Return a paginated style `Response` object for the given output data."""
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

    def paginate_queryset(self, queryset, request, view=None):
        """
        Paginate a queryset if required, either returning a page object,
        or `None` if pagination is not configured for this view.

        """
        if isinstance(queryset, filter):
            queryset = list(queryset)

        return super().paginate_queryset(queryset, request, view)


class EnterpriseCustomerSupportViewSet(EnterpriseReadOnlyModelViewSet):
    """
    API views for the ``enterprise-customer-support`` API endpoint.
    """

    queryset = models.PendingEnterpriseCustomerUser.objects.all()
    filter_backends = (DjangoFilterBackend, filters.OrderingFilter)
    permission_classes = (permissions.IsAuthenticated,)
    paginator = EnterpriseCustomerSupportPaginator()

    ordering_fields = ["is_admin", "username", "pending_enterprise_customer"]

    def filter_queryset_by_user_query(self, queryset):
        """
        Filter queryset based on user provided query
        """
        user_query = self.request.query_params.get("user_query", None)

        if user_query:
            queryset = queryset.filter(Q(user_email__icontains=user_query) | Q(username__icontains=user_query))
        return queryset

    def retrieve(self, request, *args, **kwargs):
        """
        Filter down the queryset of groups available to the requesting uuid.
        """
        enterprise_uuid = kwargs.get("enterprise_uuid", None)
        ecs_queryset = models.EnterpriseCustomerSupportUsersView.objects.all()

        try:
            ecs_queryset = self.filter_queryset_by_user_query(
                ecs_queryset.filter(enterprise_customer_id=enterprise_uuid)
            )
        except ValidationError:
            # did not find UUID match in either EnterpriseCustomerUser or PendingEnterpriseCustomerUser
            return response.Response(
                {"detail": "Could not find enterprise uuid {}".format(enterprise_uuid)},
                status=status.HTTP_404_NOT_FOUND,
            )

        # default sort criteria
        is_reversed = False
        ordering_criteria = self.request.query_params.get("ordering", None)
        if ordering_criteria:
            is_reversed = ordering_criteria.startswith('-')
            if is_reversed:
                ordering_criteria = ordering_criteria[1:]

        order_by_admin = f"{('-' if is_reversed else '')}is_admin"
        order_by_username_or_email = Case(
            When(is_pending=True, then=F('user_email')),
            default=F('username'),
            output_field=CharField()
        )
        if ordering_criteria in ("administrator", "learner"):
            # Sort by admin status
            ecs_queryset = ecs_queryset.order_by(order_by_admin)
        elif ordering_criteria == "details":
            # If pending user, sort by email, otherwise sort by username
            if is_reversed:
                ecs_queryset = ecs_queryset.order_by(order_by_username_or_email.desc())
            else:
                ecs_queryset = ecs_queryset.order_by(order_by_username_or_email.asc())
        elif not ordering_criteria:
            # Apply default ordering criteria (first by is_admin,
            # then username) only if user does not specify ordering criteria;
            ecs_queryset = ecs_queryset.order_by('-is_admin', order_by_username_or_email.asc())
        users_page = self.paginator.paginate_queryset(ecs_queryset, request, view=self)

        serializer = serializers.EnterpriseUserSerializer(users_page, many=True)
        serializer_data = serializer.data

        return self.paginator.get_paginated_response(serializer_data)
