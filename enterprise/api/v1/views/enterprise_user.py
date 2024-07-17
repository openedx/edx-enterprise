"""
Views for the ``enterprise-user`` API endpoint.
"""

from django.core.exceptions import ValidationError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, response, status

from enterprise import models
from enterprise.api.v1 import serializers
from enterprise.api.v1.views.base_views import EnterpriseReadOnlyModelViewSet
from enterprise.logging import getEnterpriseLogger

LOGGER = getEnterpriseLogger(__name__)


class EnterpriseUserViewSet(EnterpriseReadOnlyModelViewSet):
    """
    API views for the ``enterprise-user`` API endpoint.
    """
    queryset = models.EnterpriseCustomerUser.objects.all()
    filter_backends = (filters.OrderingFilter, DjangoFilterBackend,)
    serializer_class = serializers.EnterpriseUserSerializer
    permission_classes = (permissions.IsAuthenticated,)

    USER_ID_FILTER = 'enterprise_customer_users__user_id'
    FILTER_FIELDS = (
        'user_id',
    )
    ORDER_FIELDS = (
        'user_id',
        'user_name',
        'enterprise_customer__contact_email'
    )

    filterset_fields = FILTER_FIELDS
    ordering_fields = ORDER_FIELDS


    def retrieve(self, request, *args, **kwargs):  # pylint: disable=unused-argument
        """
        - Filter down the queryset of groups available to the requesting uuid.
        """
        enterprise_uuid = kwargs.get('enterprise_uuid', None)
        try:
            queryset = self.queryset.filter(enterprise_customer__uuid=enterprise_uuid)
            serializer = self.serializer_class(queryset, many=True)
            return response.Response(serializer.data)

        except ValidationError:
            return response.Response(
                {'detail': f'Could not find enterprise uuid {enterprise_uuid}'},
                status=status.HTTP_404_NOT_FOUND
            )
