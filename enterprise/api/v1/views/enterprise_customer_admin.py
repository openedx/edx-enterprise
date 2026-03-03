
"""
Views for `EnterpriseCustomerAdmin` model.
"""
import logging

from edx_rbac.decorators import permission_required
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404

from enterprise import models, roles_api
from enterprise.api import utils as admin_utils
from enterprise.api.v1.serializers import AdminInviteSerializer, EnterpriseCustomerAdminSerializer
from enterprise.constants import (
    ACTIVE_ADMIN_ROLE_TYPE,
    ENTERPRISE_ADMIN_ROLE,
    ENTERPRISE_CUSTOMER_PROVISIONING_ADMIN_ACCESS_PERMISSION,
    PENDING_ADMIN_ROLE_TYPE,
)

logger = logging.getLogger(__name__)

User = get_user_model()


def get_enterprise_uuid_for_delete_admin(request, *args, **kwargs):
    """
    Helper function to extract enterprise_customer_uuid from customer_id for permission validation.

    Args:
        request: The HTTP request object
        args: Positional arguments
        kwargs: Keyword arguments containing 'customer_id'

    Returns:
        str: The enterprise customer UUID if found, None otherwise
    """
    customer_id = kwargs.get('customer_id')
    role = request.query_params.get('role') or request.data.get('role')

    if not customer_id or not role:
        return None

    role = role.lower()

    try:
        if role == PENDING_ADMIN_ROLE_TYPE:
            pending_admin = models.PendingEnterpriseCustomerAdminUser.objects.select_related(
                'enterprise_customer'
            ).get(id=int(customer_id))
            return str(pending_admin.enterprise_customer.uuid)
        elif role == ACTIVE_ADMIN_ROLE_TYPE:
            enterprise_customer_user = models.EnterpriseCustomerUser.objects.select_related(
                'enterprise_customer'
            ).get(id=int(customer_id))
            return str(enterprise_customer_user.enterprise_customer.uuid)
    except (ValueError, TypeError, models.PendingEnterpriseCustomerAdminUser.DoesNotExist,
            models.EnterpriseCustomerUser.DoesNotExist):
        return None

    return None


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
        fn=get_enterprise_uuid_for_delete_admin,
    )
    @action(
        detail=False,
        methods=['delete'],
        url_path=r'(?P<customer_id>[^/.]+)/delete'
    )
    def delete_admin(self, request, customer_id=None):
        """
        Delete an admin record based on role.

        DELETE /enterprise/api/v1/enterprise-customer-admin/{customer_id}/delete/?role=<role>

        Path Parameters:

        - ``customer_id``: ID of the admin record to delete (PendingEnterpriseCustomerAdminUser ID
          or EnterpriseCustomerUser ID)

        Query Parameters:

        - ``role``: Either 'pending' or 'admin' (required, case-insensitive)

        Based on the role query parameter:

        - If role='pending': Hard deletes PendingEnterpriseCustomerAdminUser where id=customer_id
        - If role='admin': Deletes role assignment from SystemWideEnterpriseUserRoleAssignment
          for the EnterpriseCustomerUser id=customer_id, and deactivates
          EnterpriseCustomerUser if no other roles exist

        Returns:
            200 OK with success message and user_deactivated flag (for active admins)
            400 BAD REQUEST if role parameter is missing or invalid
            404 NOT FOUND if the specified admin record doesn't exist
        """
        # Validate customer_id is a valid integer
        try:
            customer_id_int = int(customer_id)
        except (ValueError, TypeError):
            return self._error_response(
                'customer_id must be a valid integer',
                status.HTTP_400_BAD_REQUEST
            )

        role = request.query_params.get('role') or request.data.get('role')

        if not role:
            return self._error_response(
                f'role parameter is required ({PENDING_ADMIN_ROLE_TYPE} or {ACTIVE_ADMIN_ROLE_TYPE})',
                status.HTTP_400_BAD_REQUEST
            )

        role = role.lower()

        if role == PENDING_ADMIN_ROLE_TYPE:
            return self._delete_pending_admin(customer_id_int)
        elif role == ACTIVE_ADMIN_ROLE_TYPE:
            return self._delete_active_admin(customer_id_int)
        else:
            return self._error_response(
                f'Invalid role. Must be "{PENDING_ADMIN_ROLE_TYPE}" or "{ACTIVE_ADMIN_ROLE_TYPE}"',
                status.HTTP_400_BAD_REQUEST
            )

    def _error_response(self, message, status_code):
        """Helper method to create error responses."""
        return Response({'error': message}, status=status_code)

    @transaction.atomic
    def _delete_pending_admin(self, customer_id):
        """
        Delete a pending admin invitation.

        Args:
            customer_id: ID of the PendingEnterpriseCustomerAdminUser record

        Returns:
            Response object with success or error message
        """
        try:
            pending_admin = models.PendingEnterpriseCustomerAdminUser.objects.select_related(
                'enterprise_customer'
            ).get(id=customer_id)
            enterprise_customer = pending_admin.enterprise_customer
            user_email = pending_admin.user_email

            pending_admin.delete()
            logger.info(
                "Hard deleted PendingEnterpriseCustomerAdminUser id=%s for enterprise %s",
                customer_id,
                enterprise_customer.uuid
            )
            return Response(
                {'message': f'Pending admin invitation for {user_email} deleted successfully'},
                status=status.HTTP_200_OK
            )
        except models.PendingEnterpriseCustomerAdminUser.DoesNotExist:
            return self._error_response(
                'Pending admin invitation not found',
                status.HTTP_404_NOT_FOUND
            )

    @transaction.atomic
    def _delete_active_admin(self, customer_id):
        """
        Delete an active admin by removing their role assignment.

        Args:
            customer_id: ID of the EnterpriseCustomerUser record

        Returns:
            Response object with success message and user_deactivated flag
        """
        try:
            enterprise_customer_user = models.EnterpriseCustomerUser.objects.select_related(
                'enterprise_customer', 'user_fk'
            ).get(id=customer_id)
        except models.EnterpriseCustomerUser.DoesNotExist:
            return self._error_response('Admin user not found', status.HTTP_404_NOT_FOUND)

        # Verify admin record exists
        if not models.EnterpriseCustomerAdmin.objects.filter(
            enterprise_customer_user=enterprise_customer_user
        ).exists():
            return self._error_response('Admin record not found', status.HTTP_404_NOT_FOUND)

        enterprise_customer = enterprise_customer_user.enterprise_customer
        user = enterprise_customer_user.user_fk

        # Check if admin role assignment exists
        role_assignment = models.SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user=user,
            enterprise_customer=enterprise_customer,
            role__name=ENTERPRISE_ADMIN_ROLE,
        )

        if not role_assignment.exists():
            return self._error_response(
                'Admin role assignment not found',
                status.HTTP_404_NOT_FOUND
            )

        # Delete the admin role
        deleted_count, _ = role_assignment.delete()
        logger.info(
            "Deleted %d admin role assignment(s) for user %s in enterprise %s",
            deleted_count,
            user.id,
            enterprise_customer.uuid
        )

        # Check if user has other roles for this enterprise with row-level locking to prevent race conditions
        has_other_roles = models.SystemWideEnterpriseUserRoleAssignment.objects.select_for_update().filter(
            user=user,
            enterprise_customer=enterprise_customer,
        ).exists()

        # Deactivate EnterpriseCustomerUser if no other roles exist (soft delete)
        user_deactivated = False
        if not has_other_roles:
            enterprise_customer_user.active = False
            enterprise_customer_user.save(update_fields=['active', 'modified'])
            user_deactivated = True
            logger.info(
                "Deactivated EnterpriseCustomerUser id=%s for user %s in enterprise %s (no other roles)",
                enterprise_customer_user.id,
                user.id,
                enterprise_customer.uuid
            )
        else:
            logger.info(
                "Kept EnterpriseCustomerUser id=%s active for user %s (has other roles)",
                enterprise_customer_user.id,
                user.id
            )

        # Create meaningful message with email
        user_identifier = user.email or user.username
        message = (
            f'Admin {user_identifier} deleted successfully and user account deactivated'
            if user_deactivated else
            f'Admin {user_identifier} deleted successfully'
        )

        return Response(
            {
                'message': message,
                'user_deactivated': user_deactivated
            },
            status=status.HTTP_200_OK
        )

    @permission_required(
        ENTERPRISE_CUSTOMER_PROVISIONING_ADMIN_ACCESS_PERMISSION,
        fn=lambda request, *args, **kwargs: kwargs.get('enterprise_customer_uuid'),
    )
    @action(
        detail=False,
        methods=["post"],
        url_path=r"(?P<enterprise_customer_uuid>[0-9a-fA-F-]+)/admins/invite",
    )
    def invite_admins(self, request, **kwargs):
        """
        Invite new admins to an Enterprise Customer by sending invitation emails.

        Request data must include:

        - emails: list of email addresses to invite
        - enterprise_customer_uuid: UUID of the enterprise customer

        Returns:
            A list of dicts with email and status for each attempted invite.
        """
        enterprise_customer_uuid = kwargs.get("enterprise_customer_uuid")
        if not enterprise_customer_uuid:
            logger.warning("Missing enterprise_customer_uuid in request URL/path.")
            return Response({"detail": "Missing enterprise_customer_uuid."}, status=status.HTTP_400_BAD_REQUEST)

        enterprise_customer = get_object_or_404(models.EnterpriseCustomer, uuid=enterprise_customer_uuid)
        serializer = AdminInviteSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except serializers.ValidationError as e:
            error_detail = e.detail
            if 'emails' in error_detail:
                logger.info(
                    "No emails provided for enterprise customer: %s", enterprise_customer_uuid
                )
                # Show the custom error message from the serializer
                return Response({"detail": error_detail['emails'][0]}, status=status.HTTP_400_BAD_REQUEST)
            # Show the first error message for other fields
            return Response({"detail": str(error_detail)}, status=status.HTTP_400_BAD_REQUEST)

        normalized_emails = serializer.validated_data.get("emails", [])

        logger.info(
            "Inviting admins for enterprise customer: %s, emails: %s",
            enterprise_customer_uuid,
            normalized_emails,
        )

        # Batch prefetch to avoid N+1 queries
        existing_admin_emails = admin_utils.get_existing_admin_emails(enterprise_customer)
        existing_pending_emails = admin_utils.get_existing_pending_emails(enterprise_customer, normalized_emails)

        new_invites = [
            email for email in normalized_emails
            if email not in existing_admin_emails and email not in existing_pending_emails
        ]

        if new_invites:
            logger.info(
                "Creating new pending invites for enterprise customer: %s, emails: %s",
                enterprise_customer_uuid,
                new_invites,
            )
            try:
                admin_utils.create_pending_invites(enterprise_customer, new_invites)
            except ValueError as e:
                logger.error("Failed to create pending invites: %s", str(e))
                return Response(
                    {"detail": "Failed to create pending invites."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        response_data = []
        for email in normalized_emails:
            status_str = admin_utils.get_invite_status(email, existing_admin_emails, existing_pending_emails)
            response_data.append({"email": email, "status": status_str})

        logger.info(
            "Invite response for enterprise customer: %s, response: %s",
            enterprise_customer_uuid,
            response_data,
        )
        return Response(response_data, status=status.HTTP_200_OK)
