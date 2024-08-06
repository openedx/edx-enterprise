
"""
Views for the ``enterprise-user`` API endpoint.
"""

from collections import OrderedDict

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, response, status
from rest_framework.pagination import PageNumberPagination

from django.core.exceptions import ValidationError

from enterprise import models
from enterprise.api.v1 import serializers
from enterprise.api.v1.views.base_views import EnterpriseReadOnlyModelViewSet
from enterprise.logging import getEnterpriseLogger

LOGGER = getEnterpriseLogger(__name__)


class EnterpriseCustomerSupportPaginator(PageNumberPagination):
    """Custom paginator for the enterprise customer support."""
    page_size = 8

    def get_paginated_response(self, data):
        """Return a paginated style `Response` object for the given output data."""
        return response.Response(
            OrderedDict([
                ('count', self.page.paginator.count),
                ('num_pages', self.page.paginator.num_pages),
                ('next', self.get_next_link()),
                ('previous', self.get_previous_link()),
                ('results', data),
            ])
        )

    def paginate_queryset(self, queryset, request, view=None):
        """
        Paginate a queryset if required, either returning a page object,
        or `None` if pagination is not configured for this view.

        This method is a modified version of the original `paginate_queryset` method
        from the `PageNumberPagination` class. The original method was modified to
        handle the case where the `queryset` is a `filter` object.
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

    ordering_fields = ['id']
    filterset_fields = ['user_email']

    def filter_by_email(self, data):
        """
        Filter dataset by email
        """
        filter_email = self.request.query_params.get('user_email', None)

        if filter_email:
            results = []
            for elem in data:
                if (
                    elem['enterprise_customer_user'] and
                    elem['enterprise_customer_user']['email'] == filter_email
                ):
                    results.append(elem)

                elif (
                    elem['pending_enterprise_customer_user'] and
                    elem['pending_enterprise_customer_user']['user_email'] == filter_email
                ):
                    results.append(elem)

            return results

        else:
            return data

    def order_by_attribute(self, data):
        """
        Order by ID if passed in by user, else default to is_admin ordering
        """
        ordering_criteria = self.request.query_params.get('ordering', None)

        if ordering_criteria:
            reverse = '-' in ordering_criteria
            data = sorted(
                data,
                key=(
                    lambda k:
                    k['enterprise_customer_user']['id']
                    if k['enterprise_customer_user']
                    else k['is_admin']
                ),
                reverse=reverse
            )
        else:
            data = sorted(
                data,
                key=lambda k: k['is_admin'],
                reverse=True
            )

        return data

    def retrieve(self, request, *args, **kwargs):
        """
        - Filter down the queryset of groups available to the requesting uuid.
        """
        enterprise_uuid = kwargs.get('enterprise_uuid', None)
        users = []
        try:
            enterprise_customer_queryset = models.EnterpriseCustomerUser.objects.filter(
                enterprise_customer__uuid=enterprise_uuid,
            )

            users.extend(enterprise_customer_queryset)
            pending_enterprise_customer_queryset = models.PendingEnterpriseCustomerUser.objects.filter(
                enterprise_customer__uuid=enterprise_uuid
            ).order_by('user_email')
            users.extend(pending_enterprise_customer_queryset)
        except ValidationError:
            # did not find UUID match in either EnterpriseCustomerUser or  PendingEnterpriseCustomerUser
            return response.Response(
                {'detail': 'Could not find enterprise uuid {}'.format(enterprise_uuid)},
                status=status.HTTP_404_NOT_FOUND
            )

        users_page = self.paginator.paginate_queryset(
            users,
            request,
            view=self
        )
        serializer = serializers.EnterpriseUserSerializer(
            users_page,
            many=True
        )

        serializer_data = serializer.data
        # apply filter criteria
        serializer_data = self.filter_by_email(serializer_data)
        # apply order criteria
        serializer_data = self.order_by_attribute(serializer_data)

        return self.paginator.get_paginated_response(serializer_data)
