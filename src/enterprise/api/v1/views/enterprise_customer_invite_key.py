"""
Views for enterprise customer invite keys.
"""

from django_filters.rest_framework import DjangoFilterBackend
from edx_rbac.decorators import permission_required
from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from rest_framework import filters, permissions, status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_201_CREATED, HTTP_422_UNPROCESSABLE_ENTITY

from django.shortcuts import get_object_or_404

from enterprise import models
from enterprise.api.filters import EnterpriseCustomerInviteKeyFilterBackend
from enterprise.api.utils import get_ent_cust_from_enterprise_customer_key
from enterprise.api.v1 import serializers
from enterprise.api.v1.views.base_views import EnterpriseReadWriteModelViewSet
from enterprise.errors import LinkUserToEnterpriseError
from enterprise.logging import getEnterpriseLogger
from enterprise.utils import track_enterprise_user_linked

LOGGER = getEnterpriseLogger(__name__)


class EnterpriseCustomerInviteKeyViewSet(EnterpriseReadWriteModelViewSet):
    """
    API for accessing enterprise customer keys.
    """
    queryset = models.EnterpriseCustomerInviteKey.objects.all()
    authentication_classes = (JwtAuthentication, SessionAuthentication)
    permission_classes = (permissions.IsAuthenticated,)

    filter_backends = (filters.OrderingFilter, DjangoFilterBackend, EnterpriseCustomerInviteKeyFilterBackend)
    http_method_names = ['get', 'post', 'patch']

    def get_serializer_class(self):
        """
        Use a special serializer for any requests that aren't read-only.
        """
        if self.request.method in ('POST', 'DELETE'):
            return serializers.EnterpriseCustomerInviteKeyWriteSerializer

        if self.request.method == 'PATCH':
            return serializers.EnterpriseCustomerInviteKeyPartialUpdateSerializer

        return serializers.EnterpriseCustomerInviteKeyReadOnlySerializer

    def retrieve(self, request, *args, **kwargs):
        invite_key = get_object_or_404(models.EnterpriseCustomerInviteKey, pk=kwargs['pk'])
        serializer = self.get_serializer(invite_key)
        return Response(serializer.data)

    @permission_required('enterprise.can_access_admin_dashboard')
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @permission_required('enterprise.can_access_admin_dashboard')
    @action(methods=['get'], detail=False, url_path='basic-list')
    def basic_list(self, request, *args, **kwargs):
        """
        Unpaginated list of all invite keys matching the filters.
        """
        queryset = self.get_queryset()
        queryset = self.filter_queryset(queryset)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @permission_required(
        'enterprise.can_access_admin_dashboard',
        fn=lambda request: request.data.get('enterprise_customer_uuid')
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @permission_required(
        'enterprise.can_access_admin_dashboard',
        fn=lambda request, pk: get_ent_cust_from_enterprise_customer_key(pk)
    )
    def partial_update(self, request, *args, **kwargs):
        try:
            return super().partial_update(request, *args, **kwargs)
        except ValueError as ex:
            return Response({'detail': str(ex)}, status=HTTP_422_UNPROCESSABLE_ENTITY)

    @permission_required(
        'enterprise.can_access_admin_dashboard',
        fn=lambda request, pk: get_ent_cust_from_enterprise_customer_key(pk)
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    @action(methods=['post'], detail=True, url_path='link-user')
    def link_user(self, request, pk=None):
        """
        Post
        Links user using enterprise_customer_key
        /enterprise/api/enterprise-customer-invite-key/{enterprise_customer_key}/link-user

        Given a enterprise_customer_key, link user to the appropriate enterprise.

        If the key is not found, returns 404
        If the key is not valid, returns 422
        If we create an `EnterpriseCustomerUser` returns 201
        If an `EnterpriseCustomerUser` if found returns 200
        """
        enterprise_customer_key = get_object_or_404(
            models.EnterpriseCustomerInviteKey,
            uuid=pk
        )

        if not enterprise_customer_key.is_valid:
            return Response(
                {"detail": "Enterprise customer invite key is not valid"},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        enterprise_customer = enterprise_customer_key.enterprise_customer

        enterprise_user, created = models.EnterpriseCustomerUser.all_objects.get_or_create(
            user_id=request.user.id,
            enterprise_customer=enterprise_customer,
        )

        response_body = {
            "enterprise_customer_slug": enterprise_customer.slug,
            "enterprise_customer_uuid": enterprise_customer.uuid,
        }
        headers = self.get_success_headers(response_body)

        track_enterprise_user_linked(
            request.user.id,
            pk,
            enterprise_customer.uuid,
            created,
        )

        if created:
            enterprise_user.invite_key = enterprise_customer_key
            enterprise_user.save()
            return Response(response_body, status=HTTP_201_CREATED, headers=headers)

        elif not enterprise_user.active or not enterprise_user.linked:
            try:
                models.EnterpriseCustomerUser.all_objects.link_user(
                    enterprise_customer,
                    request.user.email
                )
            except LinkUserToEnterpriseError:
                return Response(status=status.HTTP_422_UNPROCESSABLE_ENTITY)

            enterprise_user.refresh_from_db()
            enterprise_user.invite_key = enterprise_customer_key
            enterprise_user.save()

        return Response(response_body, status=HTTP_200_OK, headers=headers)
