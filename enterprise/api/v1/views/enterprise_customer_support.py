
"""
Views for the ``enterprise-user`` API endpoint.
"""

from django_filters.rest_framework import DjangoFilterBackend
from edx_rest_framework_extensions.paginators import DefaultPagination
from rest_framework import permissions, response, status

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.utils.functional import cached_property

from enterprise import models
from enterprise.api.v1 import serializers
from enterprise.api.v1.views.base_views import EnterpriseReadOnlyModelViewSet
from enterprise.logging import getEnterpriseLogger

LOGGER = getEnterpriseLogger(__name__)


class PaginatorWithFixedCount(Paginator):
    @cached_property
    def count(self):
        return 8

class EnterpriseCustomerSupportPagination(DefaultPagination):
    django_paginator_class = PaginatorWithFixedCount

class EnterpriseCustomerSupportViewSet(EnterpriseReadOnlyModelViewSet):
    """
    API views for the ``enterprise-user`` API endpoint.
    """
    queryset = models.EnterpriseCustomerUser.objects.all()
    filter_backends = (DjangoFilterBackend,)
    permission_classes = (permissions.IsAuthenticated,)
    pagination_class = EnterpriseCustomerSupportPagination

    USER_ID_FILTER = 'enterprise_customer_users__user_id'

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
        serializer = serializers.EnterpriseUserSerializer(
            users,
            many=True
        )
        serializer_data = sorted(
            serializer.data, key=lambda k: k['is_admin'], reverse=True)
        return response.Response(serializer_data)
