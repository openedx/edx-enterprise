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
    filter_backends = (DjangoFilterBackend,)
    permission_classes = (permissions.IsAuthenticated,)

    USER_ID_FILTER = 'enterprise_customer_users__user_id'

    def retrieve(self, request, *args, **kwargs):
        """
        - Filter down the queryset of groups available to the requesting uuid.
        """
        enterprise_uuid = kwargs.get('enterprise_uuid', None)

        try:
            enterprise_customer_queryset = models.EnterpriseCustomerUser.objects.filter(
                enterprise_customer__uuid=enterprise_uuid
            )

            if enterprise_customer_queryset.exists():
                serializer = serializers.EnterpriseUserSerializer(enterprise_customer_queryset, many=True)
                return response.Response(serializer.data)

        except ValidationError:
            # did not find UUID match in EnterpriseCustomerUser, try in PendingEnterpriseCustomerUser
            pass

        try:
            pending_enterprise_customer_queryset = models.PendingEnterpriseCustomerUser.objects.filter(
                enterprise_customer_id=enterprise_uuid
            )

            if pending_enterprise_customer_queryset.exists():
                serializer = serializers.EnterprisePendingCustomerUserSerializer(
                    pending_enterprise_customer_queryset,
                    many=True
                )
                return response.Response(serializer.data)

        except ValidationError:
            # did not find UUID match in either EnterpriseCustomerUser or  PendingEnterpriseCustomerUser
            pass

        return response.Response(
            {'detail': 'Could not find enterprise uuid {}'.format(enterprise_uuid)},
            status=status.HTTP_404_NOT_FOUND
        )
