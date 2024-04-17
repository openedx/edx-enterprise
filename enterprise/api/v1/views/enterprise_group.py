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

from enterprise import constants, models, rules, utils
from enterprise.api.utils import get_enterprise_customer_from_enterprise_group_id
from enterprise.api.v1 import serializers
from enterprise.api.v1.views.base_views import EnterpriseReadWriteModelViewSet
from enterprise.logging import getEnterpriseLogger
from enterprise.tasks import send_group_membership_invitation_notification, send_group_membership_removal_notification
from enterprise.utils import localized_utcnow

LOGGER = getEnterpriseLogger(__name__)

User = auth.get_user_model()


class EnterpriseGroupViewSet(EnterpriseReadWriteModelViewSet):
    """
    API views for the ``enterprise-group`` API endpoint.
    """
    queryset = models.EnterpriseGroup.objects.all()
    queryset_with_removed = models.EnterpriseGroup.all_objects.all()
    permission_classes = (permissions.IsAuthenticated,)
    filter_backends = (filters.OrderingFilter, DjangoFilterBackend,)
    serializer_class = serializers.EnterpriseGroupSerializer

    def get_queryset(self, **kwargs):
        """
        - Filter down the queryset of groups available to the requesting user.
        - Account for requested filtering query params
        """
        include_deleted = self.request.query_params.get('include_deleted', False)
        if include_deleted:
            queryset = self.queryset_with_removed
        else:
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
    def get_learners(self, request, *args, **kwargs):
        """
        Endpoint Location to return all learners: GET api/v1/enterprise-group/<group_uuid>/learners/

        Endpoint Location to return pending learners:
        GET api/v1/enterprise-group/<group_uuid>/learners/?pending_users_only=true

        Request Arguments:
        - ``group_uuid`` (URL location, required): The uuid of the group from which learners should be listed.

        Optional query params:
        - ``pending_users_only`` (string, optional): Specify that results should only contain pending learners
        - ``q`` (string, optional): Filter the returned members by user email and name with a provided sub-string
        - ``sort_by`` (string, optional): Specify how the returned members should be ordered. Supported sorting values
        are `memberDetails`, `memberStatus`, and `recentAction`. Ordering can be reversed by supplying a `-` at the
        beginning of the sorting value ie `-memberStatus`.
        - ``page`` (int, optional): Which page of paginated data to return.

        Returns: Paginated list of learners that are associated with the enterprise group uuid::

            {
                'count': 1,
                'next': null,
                'previous': null,
                'results': [
                    {
                        'learner_id': integer or None,
                        'pending_learner_id': integer or None,
                        'enterprise_group_membership_uuid': UUID,
                        'member_details': {
                            'user_email': string,
                            'user_name': string,
                        },
                        'recent_action': string,
                        'status': string,
                    },
                ],
            }

        """
        query_params = self.request.query_params.copy()
        is_reversed = bool(query_params.get('is_reversed', False))

        param_serializers = serializers.EnterpriseGroupLearnersRequestQuerySerializer(
            data=query_params
        )

        if not param_serializers.is_valid():
            return Response(param_serializers.errors, status=400)

        user_query = param_serializers.validated_data.get('user_query')
        sort_by = param_serializers.validated_data.get('sort_by')
        pending_users_only = param_serializers.validated_data.get('pending_users_only')

        group_uuid = kwargs.get('group_uuid')
        try:
            group_object = self.get_queryset().get(uuid=group_uuid)
            members = group_object.get_all_learners(user_query,
                                                    sort_by,
                                                    desc_order=is_reversed,
                                                    pending_users_only=pending_users_only)

            page = self.paginate_queryset(members)
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

        Request Arguments:
        - ``learner_emails``: List of learner emails to associate with the group. Note: only processes the first
        1000 records provided.

        Optional request data:
        - ``act_by_date`` (datetime, optional): The expiration date for the subsidy.
        - ``catalog_uuid`` (string, optional): The uuid of the catalog that is part of the subsidy.

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
        param_serializer = serializers.EnterpriseGroupRequestDataSerializer(data=request.data)
        param_serializer.is_valid(raise_exception=True)
        # act_by_date and catalog_uuid values are needed for Braze email trigger properties
        act_by_date = param_serializer.validated_data.get('act_by_date')
        catalog_uuid = param_serializer.validated_data.get('catalog_uuid')
        learner_emails = param_serializer.validated_data.get('learner_emails')
        total_records_processed = 0
        total_existing_users_processed = 0
        total_new_users_processed = 0
        for user_email_batch in utils.batch(learner_emails[: 1000], batch_size=200):
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
                    activated_at=localized_utcnow(),
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
            models.PendingEnterpriseCustomerUser.objects.bulk_create(pecu_records, ignore_conflicts=True)
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
        membership_uuids = [membership.uuid for membership in memberships]
        if act_by_date and catalog_uuid:
            for membership_uuid_batch in utils.batch(membership_uuids, batch_size=200):
                send_group_membership_invitation_notification.delay(
                    customer.uuid,
                    membership_uuid_batch,
                    act_by_date,
                    catalog_uuid
                )
        return Response(data, status=201)

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

        Optional request data:
            - ``catalog_uuid`` (string, optional): The uuid of the catalog that is part of the subsidy.

        Returns:
            - ``records_deleted``:
                Number of membership records removed
        """
        try:
            group = self.get_queryset().get(uuid=group_uuid)
            customer = group.enterprise_customer
        except models.EnterpriseGroup.DoesNotExist as exc:
            raise Http404 from exc
        param_serializer = serializers.EnterpriseGroupRequestDataSerializer(data=request.data)
        param_serializer.is_valid(raise_exception=True)

        catalog_uuid = param_serializer.validated_data.get('catalog_uuid')
        learner_emails = param_serializer.validated_data.get('learner_emails')

        records_deleted = 0
        for user_email_batch in utils.batch(learner_emails[: 1000], batch_size=200):
            existing_users = User.objects.filter(email__in=user_email_batch).values_list("id", flat=True)
            group_q = Q(group=group)
            ecu_in_q = Q(enterprise_customer_user__user_id__in=existing_users)
            pecu_in_q = Q(pending_enterprise_customer_user__user_email__in=user_email_batch)
            records_to_delete = models.EnterpriseGroupMembership.objects.filter(
                group_q & (ecu_in_q | pecu_in_q),
            )
            records_deleted += len(records_to_delete)
            records_to_delete_uuids = [record.uuid for record in records_to_delete]
            records_to_delete.delete()
            for records_to_delete_uuids_batch in utils.batch(records_to_delete_uuids, batch_size=200):
                send_group_membership_removal_notification.delay(
                    customer.uuid,
                    records_to_delete_uuids_batch,
                    catalog_uuid)
            # Woohoo! Records removed! Now to update the soft deleted records
            deleted_records = models.EnterpriseGroupMembership.all_objects.filter(
                uuid__in=records_to_delete_uuids,
            )
            deleted_records.update(
                status=constants.GROUP_MEMBERSHIP_REMOVED_STATUS,
                removed_at=localized_utcnow()
            )
        data = {
            'records_deleted': records_deleted,
        }
        return Response(data, status=200)
