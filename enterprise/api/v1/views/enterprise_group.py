"""
Views for the ``enterprise-group`` API endpoint.
"""

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions
from rest_framework.decorators import action

from django.db.models import Q
from django.http import Http404

from enterprise import models
from enterprise.api.v1 import serializers
from enterprise.api.v1.views.base_views import EnterpriseReadWriteModelViewSet
from enterprise.logging import getEnterpriseLogger

LOGGER = getEnterpriseLogger(__name__)


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

    @action(detail=True, methods=['get'])
    def get_learners(self, *args, **kwargs):
        """
        Endpoint Location: GET api/v1/enterprise-group/<group_uuid>/learners/

        Request Arguments:
        - ``group_uuid`` (URL location, required): The uuid of the group from which learners should be listed.

        Returns: Paginated list of learners that are associated with the enterprise group uuid::

            {
                'count': 1,
                'next': null,
                'previous': null,
                'results': [
                    {
                        'learner_uuid': 'enterprise_customer_user_id',
                        'pending_learner_id': 'pending_enterprise_customer_user_id',
                        'enterprise_group_membership_uuid': 'enterprise_group_membership_uuid',
                    },
                ],
            }

        """

        group_uuid = kwargs.get('group_uuid')
        try:
            learner_list = self.get_queryset().get(uuid=group_uuid).members.all()
            page = self.paginate_queryset(learner_list)
            serializer = serializers.EnterpriseGroupMembershipSerializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            return response

        except models.EnterpriseGroup.DoesNotExist as exc:
            LOGGER.warning(f"group_uuid {group_uuid} does not exist")
            raise Http404 from exc
