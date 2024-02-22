"""
Views for the ``enterprise-group`` API endpoint.
"""

from django_filters.rest_framework import DjangoFilterBackend
from edx_rbac.decorators import permission_required
from rest_framework import filters, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from django.contrib import auth
from django.db.models import Q
from django.http import Http404

from enterprise import models, rules, utils
from enterprise.api.utils import get_enterprise_customer_from_enterprise_group_id
from enterprise.api.v1 import serializers
from enterprise.api.v1.views.base_views import EnterpriseReadWriteModelViewSet
from enterprise.logging import getEnterpriseLogger

LOGGER = getEnterpriseLogger(__name__)

User = auth.get_user_model()


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

        if self.request.method == 'GET':
            if learner_ids := self.request.query_params.getlist('learner_ids'):
                # groups can apply to both existing and pending users
                queryset = queryset.filter(
                    Q(members__enterprise_customer_user__in=learner_ids) |
                    Q(members__pending_enterprise_customer_user__in=learner_ids),
                )
            if enterprise_uuids := self.request.query_params.getlist('enterprise_uuids'):
                queryset = queryset.filter(enterprise_customer__in=enterprise_uuids)
        return queryset

    @permission_required(
        'enterprise.can_access_admin_dashboard',
        fn=lambda request, *args, **kwargs: get_enterprise_customer_from_enterprise_group_id(kwargs['pk'])
    )
    def update(self, request, *args, **kwargs):
        """
        PATCH /enterprise/api/v1/enterprise-group/<group uuid>
        """
        if requested_customer := self.request.data.get('enterprise_customer'):
            # Essentially checking ``enterprise.can_access_admin_dashboard`` but for the customer the requester is
            # attempting to update the group record to.
            implicit_access = rules.has_implicit_access_to_dashboard(self.request.user, requested_customer)
            explicit_access = rules.has_explicit_access_to_dashboard(self.request.user, requested_customer)
            if not implicit_access and not explicit_access:
                return Response('Unauthorized', status=401)
        return super().update(request, *args, **kwargs)

    @permission_required(
        'enterprise.can_access_admin_dashboard',
        fn=lambda request, *args, **kwargs: request.POST.dict().get('enterprise_customer')
    )
    def create(self, request, *args, **kwargs):
        """
        POST /enterprise/api/v1/enterprise-group/
        """
        return super().create(request, *args, **kwargs)

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

    @action(methods=['post'], detail=False, permission_classes=[permissions.IsAuthenticated])
    @permission_required(
        'enterprise.can_access_admin_dashboard',
        fn=lambda request, group_uuid: get_enterprise_customer_from_enterprise_group_id(group_uuid)
    )
    def assign_learners(self, request, group_uuid):
        """
        POST /enterprise/api/v1/enterprise-group/<group uuid>/assign_learners

        Required Arguments:
        - ``learner_emails``: List of learner emails to associate with the group. Note: only processes the first
        1000 records provided.

        Returns:
        - ``records_processed``: Total number of group membership records processed.
        - ``new_learners``: Total number of group membership records associated with new pending enterprise learners
        that were processed.
        - ``existing_learners``: Total number of group membership records associated with existing enterprise learners
        that were processed.

        """
        try:
            group = self.get_queryset().get(uuid=group_uuid)
            customer = group.enterprise_customer
        except models.EnterpriseGroup.DoesNotExist as exc:
            raise Http404 from exc
        if requested_emails := request.POST.dict().get('learner_emails'):
            total_records_processed = 0
            total_existing_users_processed = 0
            total_new_users_processed = 0
            for user_email_batch in utils.batch(requested_emails.rstrip(',').split(',')[: 1000], batch_size=200):
                user_emails_to_create = []
                memberships_to_create = []
                # ecus: enterprise customer users
                ecus = []
                # Gather all existing User objects associated with the email batch
                existing_users = User.objects.filter(email__in=user_email_batch)

                # Build and create a list of EnterpriseCustomerUser objects for the emails of existing Users
                # Ignore conflicts in case any of the ent customer user objects already exist
                ecu_by_email = {
                    user.email: models.EnterpriseCustomerUser(
                        enterprise_customer=customer, user_id=user.id, active=True
                    ) for user in existing_users
                }
                models.EnterpriseCustomerUser.objects.bulk_create(
                    ecu_by_email.values(),
                    ignore_conflicts=True,
                )

                # Fetch all ent customer users related to existing users provided by requester
                # whether they were created above or already existed
                ecus.extend(
                    models.EnterpriseCustomerUser.objects.filter(
                        user_id__in=existing_users.values_list('id', flat=True)
                    )
                )

                # Extend the list of emails that don't have User objects associated and need to be turned into
                # new PendingEnterpriseCustomerUser objects
                user_emails_to_create.extend(set(user_email_batch).difference(set(ecu_by_email.keys())))

                # Extend the list of memberships that need to be created associated with existing Users
                ent_customer_users = [
                    models.EnterpriseGroupMembership(
                        enterprise_customer_user=ecu,
                        group=group
                    )
                    for ecu in ecus
                ]
                total_existing_users_processed += len(ent_customer_users)
                memberships_to_create.extend(ent_customer_users)

            # Go over (in batches) all emails that don't have User objects
            for emails_to_create_batch in utils.batch(user_emails_to_create, batch_size=200):
                # Create the PendingEnterpriseCustomerUser objects
                pecu_records = [
                    models.PendingEnterpriseCustomerUser(
                        enterprise_customer=customer, user_email=user_email
                    ) for user_email in emails_to_create_batch
                ]
                # According to Django docs, bulk created objects can't be used in future bulk creates as the in memory
                # objects returned by bulk_create won't have PK's assigned.
                models.PendingEnterpriseCustomerUser.objects.bulk_create(pecu_records)
                pecus = models.PendingEnterpriseCustomerUser.objects.filter(
                    user_email__in=emails_to_create_batch,
                    enterprise_customer=customer,
                )
                total_new_users_processed += len(pecus)
                # Extend the list of memberships that need to be created associated with the new pending users
                memberships_to_create.extend([
                    models.EnterpriseGroupMembership(
                        pending_enterprise_customer_user=pecu,
                        group=group
                    ) for pecu in pecus
                ])

            # Create all our memberships, bulk_create will batch for us.
            memberships = models.EnterpriseGroupMembership.objects.bulk_create(
                memberships_to_create, ignore_conflicts=True
            )
            total_records_processed += len(memberships)
            data = {
                'records_processed': total_records_processed,
                'new_learners': total_new_users_processed,
                'existing_learners': total_existing_users_processed,
            }
            return Response(data, status=201)
        return Response(data="Error: missing request data: `learner_emails`.", status=400)

    @action(methods=['post'], detail=False, permission_classes=[permissions.IsAuthenticated])
    @permission_required(
        'enterprise.can_access_admin_dashboard',
        fn=lambda request, group_uuid: get_enterprise_customer_from_enterprise_group_id(group_uuid)
    )
    def remove_learners(self, request, group_uuid):
        """
        POST /enterprise/api/v1/enterprise-group/<group uuid>/remove_learners

        Required Arguments:
            - ``learner_emails``:
                List of learner emails to associate with the group.

        Returns:
            - ``records_deleted``:
                Number of membership records removed
        """
        try:
            group = self.get_queryset().get(uuid=group_uuid)
        except models.EnterpriseGroup.DoesNotExist as exc:
            raise Http404 from exc
        if requested_emails := request.POST.dict().get('learner_emails'):
            records_deleted = 0
            for user_email_batch in utils.batch(requested_emails.split(','), batch_size=200):
                existing_users = User.objects.filter(email__in=user_email_batch).values_list("id", flat=True)
                group_q = Q(group=group)
                ecu_in_q = Q(enterprise_customer_user__user_id__in=existing_users)
                pecu_in_q = Q(pending_enterprise_customer_user__user_email__in=user_email_batch)
                records_to_delete = models.EnterpriseGroupMembership.objects.filter(
                    group_q & (ecu_in_q | pecu_in_q),
                )
                records_deleted += len(records_to_delete)
                records_to_delete.delete()
            data = {
                'records_deleted': records_deleted,
            }
            return Response(data, status=200)
        return Response(data="Error: missing request data: `learner_emails`.", status=400)
