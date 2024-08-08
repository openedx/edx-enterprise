
"""
Views for the ``enterprise-user`` API endpoint.
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

    def filter_queryset_by_email(self, queryset, is_pending_user=False):
        """
        Filter queryset based on user provided email address
        """
        filter_email = self.request.query_params.get('user_email', None)

        if filter_email:
            if not is_pending_user:
                queryset = queryset.filter(
                    user_id__in=User.objects.filter(Q(email__icontains=filter_email))
                )
            else:
                queryset = queryset.filter(user_email=filter_email)

        return queryset

    def retrieve(self, request, *args, **kwargs):
        """
        Filter down the queryset of groups available to the requesting uuid.
        """
        enterprise_uuid = kwargs.get('enterprise_uuid', None)
        users = []

        try:
            enterprise_customer_queryset = models.EnterpriseCustomerUser.objects.filter(
                enterprise_customer__uuid=enterprise_uuid,
            )
            enterprise_customer_queryset = self.filter_queryset_by_email(enterprise_customer_queryset)
            users.extend(enterprise_customer_queryset)

            pending_enterprise_customer_queryset = models.PendingEnterpriseCustomerUser.objects.filter(
                enterprise_customer__uuid=enterprise_uuid
            ).order_by('user_email')
            pending_enterprise_customer_queryset = self.filter_queryset_by_email(
                pending_enterprise_customer_queryset,
                is_pending_user=True
            )
            users.extend(pending_enterprise_customer_queryset)

        except ValidationError:
            # did not find UUID match in either EnterpriseCustomerUser or PendingEnterpriseCustomerUser
            return response.Response(
                {'detail': 'Could not find enterprise uuid {}'.format(enterprise_uuid)},
                status=status.HTTP_404_NOT_FOUND
            )

        # default sort criteria
        is_reversed = False
        sort_field = 'first_name'

        ordering_criteria = self.request.query_params.get('ordering', None)

        # apply pre-serialization ordering by user criteria before the users
        # get divvied up by pagination
        if ordering_criteria:
            is_reversed = '-' in ordering_criteria
            sort_field = 'user_id'

        # sort the users by default or specified criteria since the queryset will get
        # split up during pagination and the post-serialization sort operations
        # will be only applied to a single page of results
        users = sorted(
            users,
            key=(
                lambda k:
                getattr(k, sort_field)
                if hasattr(k, sort_field)
                else k.id
            ),
            reverse=is_reversed
        )

        # paginate the queryset
        users_page = self.paginator.paginate_queryset(
            users,
            request,
            view=self
        )

        # serialize the paged dataset
        serializer = serializers.EnterpriseUserSerializer(
            users_page,
            many=True
        )
        serializer_data = serializer.data

        # Apply post-serialization default ordering criteria (first by is_admin,
        # then first name) only if user does not specify ordering criteria;
        # Process this after the data has been serialized since the is_admin
        # field is computed/available only after serialization step
        if not ordering_criteria:
            serializer_data = sorted(
                serializer_data,
                key=lambda k: (
                    # sort by is_admin = True first (i.e. -1),
                    # then sort by first_name lexicographically
                    (-1 * k['is_admin'], k['enterprise_customer_user']['first_name'])
                    if k['enterprise_customer_user'] is not None
                    else -1 * k['is_admin']
                )
            )

        return self.paginator.get_paginated_response(serializer_data)
