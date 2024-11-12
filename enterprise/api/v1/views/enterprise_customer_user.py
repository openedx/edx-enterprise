"""
Views for the ``enterprise-customer-user`` API endpoint.
"""
from collections import OrderedDict

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from rest_framework.response import Response

from enterprise import models
from enterprise.api.filters import EnterpriseCustomerUserFilterBackend
from enterprise.api.pagination import PaginationWithFeatureFlags
from enterprise.api.v1 import serializers
from enterprise.api.v1.views.base_views import EnterpriseReadWriteModelViewSet
from enterprise.toggles import enterprise_features


def _single_page_pagination(results):
    return OrderedDict([
        ('count', len(results)),
        ('next', None),
        ('previous', None),
        ('results', results),
        ('enterprise_features', enterprise_features()),
    ])


class EnterpriseCustomerUserViewSet(EnterpriseReadWriteModelViewSet):
    """
    API views for the ``enterprise-learner`` API endpoint.
    """

    queryset = models.EnterpriseCustomerUser.objects.all()
    filter_backends = (filters.OrderingFilter, DjangoFilterBackend, EnterpriseCustomerUserFilterBackend)
    pagination_class = PaginationWithFeatureFlags

    FIELDS = (
        'enterprise_customer', 'user_id', 'active',
    )
    filterset_fields = FIELDS
    ordering_fields = FIELDS + ('created',)

    def list(self, request, *args, **kwargs):
        """
        Enterprise Customer User's Basic data list without pagination

        Besides what is laid out in filterset_fields and ordering_fields the following parameters are supported:
        - username_or_email: filter by name or email substring in a single query parameter
        - ordering=(-)username: Order by name
        """
        queryset = self.get_queryset()
        queryset = self.filter_queryset(queryset)
        serializer = self.get_serializer(queryset, many=True)
        # Manually sort by username
        final_result = serializer.data
        if ordering := request.query_params.get('ordering', None):
            if 'username' in ordering:
                def username_key(learner):
                    return learner['user']['username']
                is_descending = ordering[0] == '-'
                final_result = sorted(final_result, key=username_key, reverse=is_descending)
        paginated_result = _single_page_pagination(final_result)
        return Response(paginated_result)

    def get_serializer_class(self):
        """
        Use a flat serializer for any requests that aren't read-only.
        """
        if self.request.method in ('GET',):
            return serializers.EnterpriseCustomerUserReadOnlySerializer

        return serializers.EnterpriseCustomerUserWriteSerializer
