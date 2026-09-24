"""
Views for the ``pending-enterprise-customer-user`` API endpoint.
"""

from django_filters.rest_framework import DjangoFilterBackend
from edx_rbac.decorators import permission_required
from rest_framework import filters, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.status import HTTP_400_BAD_REQUEST

from enterprise import models
from enterprise.api.v1 import serializers
from enterprise.api.v1.views.base_views import EnterpriseReadWriteModelViewSet
from enterprise.logging import getEnterpriseLogger

LOGGER = getEnterpriseLogger(__name__)


class PendingEnterpriseCustomerUserViewSet(EnterpriseReadWriteModelViewSet):
    """
    API views for the ``pending-enterprise-learner`` API endpoint.
    Requires staff permissions
    """
    queryset = models.PendingEnterpriseCustomerUser.objects.all()
    filter_backends = (filters.OrderingFilter, DjangoFilterBackend)
    serializer_class = serializers.PendingEnterpriseCustomerUserSerializer
    permission_classes = (permissions.IsAuthenticated, permissions.IsAdminUser)

    FIELDS = (
        'enterprise_customer', 'user_email',
    )
    filterset_fields = FIELDS
    ordering_fields = FIELDS

    UNIQUE = 'unique'
    USER_EXISTS_ERROR = 'EnterpriseCustomerUser record already exists'

    def _get_return_status(self, serializer, many):
        """
        Run serializer validation and get return status
        """
        return_status = None
        serializer.is_valid(raise_exception=True)
        if not many:
            _, created = serializer.save()
            return_status = status.HTTP_201_CREATED if created else status.HTTP_204_NO_CONTENT
            return return_status

        data_list = serializer.save()
        for _, created in data_list:
            if created:
                return status.HTTP_201_CREATED
        return status.HTTP_204_NO_CONTENT

    def create(self, request, *args, **kwargs):
        """
        Creates a PendingEnterpriseCustomerUser if no EnterpriseCustomerUser for the given (customer, email)
        combination(s) exists.
        Can accept one user or a list of users.

        Returns 201 if any users were created, 204 if no users were created.
        """
        serializer = self.get_serializer(data=request.data, many=isinstance(request.data, list))
        return_status = self._get_return_status(serializer, many=isinstance(request.data, list))
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=return_status, headers=headers)


class PendingEnterpriseCustomerUserEnterpriseAdminViewSet(PendingEnterpriseCustomerUserViewSet):
    """
    Viewset for allowing enterprise admins to create linked learners
    Endpoint url: link_pending_enterprise_users/(?P<enterprise_uuid>[A-Za-z0-9-]+)/?$
    Admin must be an administrator for the enterprise in question
    """
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = serializers.LinkLearnersSerializer

    @action(methods=['post'], detail=False)
    @permission_required('enterprise.can_access_admin_dashboard', fn=lambda request, enterprise_uuid: enterprise_uuid)
    def link_learners(self, request, enterprise_uuid):
        """
        Creates a PendingEnterpriseCustomerUser if no EnterpriseCustomerUser for the given (customer, email)
        combination(s) exists.
        Can accept one user or a list of users.

        Returns 201 if any users were created, 204 if no users were created.
        """
        if not request.data:
            LOGGER.error('Empty user email payload in link_learners for enterprise: %s', enterprise_uuid)
            return Response(
                'At least one user email is required.',
                status=HTTP_400_BAD_REQUEST,
            )
        context = {'enterprise_customer__uuid': enterprise_uuid}
        serializer = self.get_serializer(
            data=request.data,
            many=isinstance(request.data, list),
            context=context,
        )
        return_status = self._get_return_status(serializer, many=isinstance(request.data, list))
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=return_status, headers=headers)
