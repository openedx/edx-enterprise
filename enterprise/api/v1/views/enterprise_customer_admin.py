"""
Views for `EnterpriseCustomerAdmin` model.
"""
from edx_rbac.decorators import permission_required
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404

from enterprise import models, roles_api
from enterprise.api.v1.serializers import EnterpriseCustomerAdminSerializer
from enterprise.constants import ENTERPRISE_ADMIN_ROLE, ENTERPRISE_CUSTOMER_PROVISIONING_ADMIN_ACCESS_PERMISSION

User = get_user_model()


class EnterpriseCustomerAdminPagination(PageNumberPagination):
    """
    Pagination class for EnterpriseCustomerAdmin viewset.
    """
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class EnterpriseCustomerAdminViewSet(
    mixins.ListModelMixin,
    mixins.UpdateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    API views for the ``enterprise-customer-admin`` API endpoint.
    Only allows GET, and PATCH requests.
    """
    queryset = models.EnterpriseCustomerAdmin.objects.all()
    serializer_class = EnterpriseCustomerAdminSerializer
    permission_classes = (IsAuthenticated,)
    pagination_class = EnterpriseCustomerAdminPagination

    def get_queryset(self):
        """
        Filter queryset to only show records for the admin user.
        Excludes admins whose EnterpriseCustomerUser has been deactivated.
        """
        return models.EnterpriseCustomerAdmin.objects.filter(
            enterprise_customer_user__user_fk=self.request.user,
            enterprise_customer_user__active=True,
        )

    @action(detail=True, methods=['post'])
    def complete_tour_flow(self, request, pk=None):  # pylint: disable=unused-argument
        """
        Add a completed tour flow to the admin's completed_tour_flows.
        POST /api/v1/enterprise-customer-admin/{pk}/complete_tour_flow/

        Request Arguments:
        - ``flow_uuid``: The request object containing the flow_uuid

        Returns: A response indicating success or failure
        """
        admin = self.get_object()
        flow_uuid = request.data.get('flow_uuid')

        if not flow_uuid:
            return Response(
                {'error': 'flow_uuid is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            flow = get_object_or_404(models.OnboardingFlow, uuid=flow_uuid)
            admin.completed_tour_flows.add(flow)

            return Response({
                'status': 'success',
                'message': f'Successfully added tour flow {flow.title} to completed flows'
            })

        except models.OnboardingFlow.DoesNotExist:
            return Response(
                {'error': f'OnboardingFlow with uuid {flow_uuid} does not exist'},
                status=status.HTTP_404_NOT_FOUND
            )

    @permission_required(
        ENTERPRISE_CUSTOMER_PROVISIONING_ADMIN_ACCESS_PERMISSION,
        fn=lambda request, *args, **kwargs: request.data.get('enterprise_customer_uuid'),
    )
    @action(detail=False, methods=['post'])
    def create_admin_by_email(self, request):
        """
        Create a new EnterpriseCustomerAdmin record based on an email address.
        The email address must match an existing user.

        POST /api/v1/enterprise-customer-admin/create_admin_by_email/

        The requesting user must have the ``enterprise_provisioning_admin``
        role to access this endpoint.

        Request Arguments:
        - ``email``: Email address of the user to make an admin
        - ``enterprise_customer_uuid``: UUID of the enterprise customer

        Returns: A response with the created admin record.
        """
        email = request.data.get('email')
        enterprise_customer_uuid = request.data.get('enterprise_customer_uuid')

        if not email:
            return Response(
                {'error': 'email is required'}, status=status.HTTP_400_BAD_REQUEST,
            )

        if not enterprise_customer_uuid:
            return Response(
                {'error': 'enterprise_customer_uuid is required'}, status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {'error': f'User with email {email} does not exist'}, status=status.HTTP_404_NOT_FOUND,
            )

        try:
            enterprise_customer = models.EnterpriseCustomer.objects.get(uuid=enterprise_customer_uuid)
        except models.EnterpriseCustomer.DoesNotExist:
            return Response(
                {'error': f'EnterpriseCustomer with uuid {enterprise_customer_uuid} does not exist'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Get or create EnterpriseCustomerUser
        enterprise_customer_user, _ = models.EnterpriseCustomerUser.objects.get_or_create(
            enterprise_customer=enterprise_customer,
            user_fk=user,
            defaults={'user_id': user.id}
        )

        response_status_code = status.HTTP_200_OK
        admin, was_created = models.EnterpriseCustomerAdmin.objects.get_or_create(
            enterprise_customer_user=enterprise_customer_user
        )
        if was_created:
            response_status_code = status.HTTP_201_CREATED

        roles_api.assign_admin_role(
            enterprise_customer_user.user,
            enterprise_customer=enterprise_customer_user.enterprise_customer
        )

        serializer = self.get_serializer(admin)
        return Response(serializer.data, status=response_status_code)

    @permission_required(
        ENTERPRISE_CUSTOMER_PROVISIONING_ADMIN_ACCESS_PERMISSION,
        fn=lambda request, enterprise_customer_uuid, *args, **kwargs: enterprise_customer_uuid,
    )
    def delete_admin(self, request, enterprise_customer_uuid=None, admin_pk=None):
        """
        Soft delete an EnterpriseCustomerAdmin record.
        DELETE /api/v1/enterprise-customer/{enterprise_customer_uuid}/admins/{admin_pk}/

        The requesting user must have the ``enterprise_provisioning_admin``
        role to access this endpoint.

        Removes the enterprise_admin role assignment and deactivates the
        EnterpriseCustomerUser if the user has no other roles for the enterprise.
        The ECA record itself is left untouched in the database.
        """
        # Validate enterprise customer
        try:
            enterprise_customer = models.EnterpriseCustomer.objects.get(uuid=enterprise_customer_uuid)
        except models.EnterpriseCustomer.DoesNotExist:
            return Response(
                {'error': f'EnterpriseCustomer with uuid {enterprise_customer_uuid} does not exist'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Look up admin record
        try:
            admin = models.EnterpriseCustomerAdmin.objects.get(pk=admin_pk)
        except models.EnterpriseCustomerAdmin.DoesNotExist:
            return Response(
                {'error': f'EnterpriseCustomerAdmin with id {admin_pk} does not exist'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Verify admin belongs to the given enterprise customer
        if admin.enterprise_customer_user.enterprise_customer_id != enterprise_customer.uuid:
            return Response(
                {'error': 'Admin does not belong to the specified enterprise customer'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Remove enterprise_admin role
        enterprise_customer_user = admin.enterprise_customer_user
        user = enterprise_customer_user.user
        roles_api.delete_admin_role_assignment(user=user, enterprise_customer=enterprise_customer)

        # Check if user has other roles for this enterprise
        has_other_roles = models.SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user=user,
            enterprise_customer=enterprise_customer,
        ).exclude(
            role__name=ENTERPRISE_ADMIN_ROLE,
        ).exists()

        # If no other roles, deactivate the EnterpriseCustomerUser
        if not has_other_roles:
            enterprise_customer_user.active = False
            enterprise_customer_user.save(update_fields=['active', 'modified'])

        return Response(status=status.HTTP_200_OK)
