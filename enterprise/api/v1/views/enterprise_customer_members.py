"""
Views for the ``enterprise-customer-members`` API endpoint.
"""

from collections import OrderedDict

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, response, status
from rest_framework.pagination import PageNumberPagination

from django.contrib import auth
from django.core.exceptions import ValidationError
from django.db.models import Q

from enterprise import models
from enterprise.api.v1 import serializers
from enterprise.api.v1.views.base_views import EnterpriseReadOnlyModelViewSet
from enterprise.logging import getEnterpriseLogger

User = auth.get_user_model()

LOGGER = getEnterpriseLogger(__name__)

class EnterpriseCustomerMembersPaginator(PageNumberPagination):
    """Custom paginator for the enterprise customer members."""

    page_size = 6

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


class EnterpriseCustomerMembersViewSet(EnterpriseReadOnlyModelViewSet):
    """
    API views for the ``enterprise-customer-members`` API endpoint.
    """

    queryset = models.PendingEnterpriseCustomerUser.objects.all()
    filter_backends = (DjangoFilterBackend, filters.OrderingFilter)
    permission_classes = (permissions.IsAuthenticated,)
    paginator = EnterpriseCustomerMembersPaginator()

    def filter_queryset_by_user_query(self, queryset, is_pending_user=False):
        """
        Filter queryset based on user provided query
        """
        user_query = self.request.query_params.get("user_query", None)
        if user_query:
            queryset = models.EnterpriseCustomerUser.objects.filter(
                user_id__in=User.objects.filter(
                    Q(email__icontains=user_query) | Q(username__icontains=user_query)
                )
            )
        return queryset

    def get_members(self, request, *args, **kwargs):
        """
        Filter down the queryset of groups available to the requesting uuid.
        """
        enterprise_uuid = kwargs.get("enterprise_uuid", None)
        users = []

        try:
            enterprise_customer_queryset = models.EnterpriseCustomerUser.objects.filter(
                enterprise_customer__uuid=enterprise_uuid,
            )
            enterprise_customer_queryset = self.filter_queryset_by_user_query(
                enterprise_customer_queryset
            )
            users.extend(enterprise_customer_queryset)

        except ValidationError:
            # did not find UUID match in either EnterpriseCustomerUser 
            return response.Response(
                {"detail": "Could not find enterprise uuid {}".format(enterprise_uuid)},
                status=status.HTTP_404_NOT_FOUND,
            )

        # default sort criteria
        is_reversed = False

        # paginate the queryset
        users_page = self.paginator.paginate_queryset(users, request, view=self)

        # serialize the paged dataset
        serializer = serializers.EnterpriseMemberSerializer(users_page, many=True)
        serializer_data = serializer.data
       
        return self.paginator.get_paginated_response(serializer_data)
