"""
Views for the ``enterprise-group`` API endpoint.
"""

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions

from django.db.models import Q

from enterprise import models
from enterprise.api.v1 import serializers
from enterprise.api.v1.views.base_views import EnterpriseReadWriteModelViewSet


class EnterpriseGroupViewSet(EnterpriseReadWriteModelViewSet):
    """
    API views for the ``enterprise-group`` API endpoint.
    """
    queryset = models.EnterpriseGroup.objects.all()
    permission_classes = (permissions.IsAuthenticated,)
    filter_backends = (filters.OrderingFilter, DjangoFilterBackend,)
    serializer_class = serializers.EnterpriseGroupSerializer

    def get_queryset(self, **kwargs):
        """
        - Filter down the queryset of groups available to the requesting user.
        - Account for requested filtering query params
        """
        queryset = self.queryset
        if not self.request.user.is_staff:
            enterprise_user_objects = models.EnterpriseCustomerUser.objects.filter(
                user_id=self.request.user.id,
                active=True,
            )
            associated_customers = []
            for user_object in enterprise_user_objects:
                associated_customers.append(user_object.enterprise_customer)
            queryset = queryset.filter(enterprise_customer__in=associated_customers)

        if self.request.method in ('GET',):
            if learner_uuids := self.request.query_params.getlist('learner_uuids'):
                # groups can apply to both existing and pending users
                queryset = queryset.filter(
                    Q(members__enterprise_customer_user__in=learner_uuids) |
                    Q(members__pending_enterprise_customer_user__in=learner_uuids),
                )
            if enterprise_uuids := self.request.query_params.getlist('enterprise_uuids'):
                queryset = queryset.filter(enterprise_customer__in=enterprise_uuids)
        return queryset
