
"""
Views for `EnterpriseCustomerAdmin` model.
"""
import logging

from edx_rbac.decorators import permission_required
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
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
        fn=lambda request, *args, **kwargs: kwargs.get('enterprise_customer_uuid'),
    )
    @action(
        detail=False,
        methods=["post"],
        url_path=r"(?P<enterprise_customer_uuid>[0-9a-fA-F-]+)/admin_invites",
        url_name="admin-invites",
    )
    def invite_admins(self, request, **kwargs):
        """
        Invite new admins to an Enterprise Customer by sending invitation emails.

        POST /enterprise/api/v1/enterprise-customer-admin/{enterprise_customer_uuid}/admin-invites

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

        try:
            enterprise_customer = get_object_or_404(models.EnterpriseCustomer, uuid=enterprise_customer_uuid)
        except ValidationError:
            logger.warning("Invalid enterprise_customer_uuid format: %s", enterprise_customer_uuid)
            return Response(
                {"detail": "enterprise_customer_uuid must be a valid UUID."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = AdminInviteSerializer(data=request.data)
        if not serializer.is_valid():
            logger.info(
                "Invalid payload for enterprise customer: %s, errors: %s",
                enterprise_customer_uuid,
                serializer.errors
            )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        normalized_emails = serializer.validated_data.get("emails", [])

        logger.info(
            "Inviting admins for enterprise customer: %s, email count: %d",
            enterprise_customer_uuid,
            len(normalized_emails),
        )

        # Batch prefetch to avoid N+1 queries
        try:
            existing_admin_emails = admin_utils.get_existing_admin_emails(enterprise_customer)
            existing_pending_emails = admin_utils.get_existing_pending_emails(
                enterprise_customer, normalized_emails
            )
        except DatabaseError as exc:
            logger.error(
                "Database error fetching admin status for enterprise %s: %s",
                enterprise_customer_uuid,
                str(exc),
                exc_info=True
            )
            return Response(
                {"detail": "Failed to retrieve admin information due to a database error."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Exclude active admins and pending invites from new invites
        new_invites = [
            email for email in normalized_emails
            if email not in existing_admin_emails
            and email not in existing_pending_emails
        ]

        # Track which emails were actually newly created (not just attempted)
        newly_created_emails = set()
        if new_invites:
            logger.info(
                "Creating new pending invites for enterprise customer: %s, new invite count: %d",
                enterprise_customer_uuid,
                len(new_invites),
            )
            try:
                with transaction.atomic():
                    created_invites = admin_utils.create_pending_invites(enterprise_customer, new_invites)
                    # Track emails that were actually created (handles race conditions in get_or_create)
                    newly_created_emails = {invite.user_email for invite in created_invites}
            except DatabaseError as exc:
                logger.error(
                    "Database error creating pending invites for enterprise %s: %s",
                    enterprise_customer_uuid,
                    str(exc),
                    exc_info=True
                )
                return Response(
                    {"detail": "Failed to create pending invites due to a database error."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        # Update existing_pending_emails with race condition results
        # Emails in new_invites but not in newly_created_emails hit a race condition
        # (get_or_create found an existing record), so add them to existing_pending_emails
        race_condition_emails = set(new_invites) - newly_created_emails
        existing_pending_emails.update(race_condition_emails)

        response_data = []
        for email in normalized_emails:
            status_str = admin_utils.get_invite_status(
                email,
                existing_admin_emails,
                existing_pending_emails
            )
            response_data.append({"email": email, "status": status_str})

        logger.info(
            "Invite response for enterprise customer: %s, total processed: %d, new invites: %d",
            enterprise_customer_uuid,
            len(response_data),
            len(new_invites),
        )
        return Response(response_data, status=status.HTTP_200_OK)

    @permission_required(
        ENTERPRISE_CUSTOMER_PROVISIONING_ADMIN_ACCESS_PERMISSION,
        fn=lambda request, *args, **kwargs: kwargs.get('enterprise_customer_uuid'),
    )
    def delete_admin(self, request, enterprise_customer_uuid=None, id=None):  # pylint: disable=redefined-builtin
        """
        Delete an admin record based on role.

        DELETE /enterprise/api/v1/enterprise-customer/{enterprise_customer_uuid}/admins/{id}/?role=<role>

        Path Parameters:

        - ``enterprise_customer_uuid``: UUID of the enterprise customer.

        - ``id``: ID of the admin record to delete (PendingEnterpriseCustomerAdminUser ID
          or EnterpriseCustomerUser ID)

        Query Parameters:

        - ``role``: Either 'pending' or 'admin' (required, case-insensitive)

        Role handling:
        ``role='pending'`` hard deletes ``PendingEnterpriseCustomerAdminUser`` where ``id=id``.
        ``role='admin'`` deletes role assignment from ``SystemWideEnterpriseUserRoleAssignment``
        for ``EnterpriseCustomerUser`` ``id=id``, and deactivates ``EnterpriseCustomerUser``
        if no other roles exist.

        Returns:
            200 OK with success message and user_deactivated flag (for active admins)
            400 BAD REQUEST if role parameter is missing or invalid
            404 NOT FOUND if the specified admin record doesn't exist
        """
        if not enterprise_customer_uuid:
            logger.warning("Missing enterprise_customer_uuid in request URL/path.")
            return Response({"detail": "Missing enterprise_customer_uuid."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            get_object_or_404(models.EnterpriseCustomer, uuid=enterprise_customer_uuid)
        except ValidationError:
            logger.warning("Invalid enterprise_customer_uuid format: %s", enterprise_customer_uuid)
            return self._error_response(
                'enterprise_customer_uuid must be a valid UUID',
                status.HTTP_400_BAD_REQUEST,
            )

        # Validate id is a valid integer
        try:
            admin_record_id = int(id)
        except (ValueError, TypeError):
            return self._error_response(
                'id must be a valid integer',
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
            try:
                return self._delete_pending_admin(enterprise_customer_uuid, admin_record_id)
            except DatabaseError:
                logger.exception(
                    "Database error deleting PendingEnterpriseCustomerAdminUser id=%s for enterprise=%s",
                    admin_record_id,
                    enterprise_customer_uuid,
                )
                return self._error_response(
                    'Failed to delete pending admin invitation due to a database error',
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        elif role == ACTIVE_ADMIN_ROLE_TYPE:
            try:
                return self._delete_active_admin(enterprise_customer_uuid, admin_record_id)
            except DatabaseError:
                logger.exception(
                    "Database error deleting active admin for EnterpriseCustomerUser id=%s in enterprise=%s",
                    admin_record_id,
                    enterprise_customer_uuid,
                )
                return self._error_response(
                    'Failed to delete admin due to a database error',
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        else:
            return self._error_response(
                f'Invalid role. Must be "{PENDING_ADMIN_ROLE_TYPE}" or "{ACTIVE_ADMIN_ROLE_TYPE}"',
                status.HTTP_400_BAD_REQUEST
            )

    def _error_response(self, message, status_code):
        """Helper method to create error responses."""
        return Response({'error': message}, status=status_code)

    @transaction.atomic
    def _delete_pending_admin(self, enterprise_customer_uuid, admin_record_id):
        """
        Delete a pending admin invitation.

        Args:
            enterprise_customer_uuid: UUID of the enterprise customer in request path
            admin_record_id: ID of the PendingEnterpriseCustomerAdminUser record

        Returns:
            Response object with success or error message
        """
        try:
            pending_admin = models.PendingEnterpriseCustomerAdminUser.objects.select_for_update().select_related(
                'enterprise_customer'
            ).get(
                id=admin_record_id,
                enterprise_customer__uuid=enterprise_customer_uuid,
            )
            enterprise_customer = pending_admin.enterprise_customer
            user_email = pending_admin.user_email

            pending_admin.delete()
            logger.info(
                "Hard deleted PendingEnterpriseCustomerAdminUser id=%s for enterprise %s",
                admin_record_id,
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
    def _delete_active_admin(self, enterprise_customer_uuid, admin_record_id):
        """
        Delete an active admin by removing their role assignment.

        Args:
            enterprise_customer_uuid: UUID of the enterprise customer in request path
            admin_record_id: ID of the EnterpriseCustomerUser record

        Returns:
            Response object with success message and user_deactivated flag
        """
        try:
            enterprise_customer_user = models.EnterpriseCustomerUser.objects.select_for_update().select_related(
                'enterprise_customer', 'user_fk'
            ).get(
                id=admin_record_id,
                active=True,
                enterprise_customer__uuid=enterprise_customer_uuid,
            )
        except models.EnterpriseCustomerUser.DoesNotExist:
            return self._error_response('Admin user not found', status.HTTP_404_NOT_FOUND)

        # Verify and lock admin record so role/admin state transitions stay consistent.
        admin_record = models.EnterpriseCustomerAdmin.objects.select_for_update().filter(
            enterprise_customer_user=enterprise_customer_user
        ).first()
        if not admin_record:
            return self._error_response('Admin record not found', status.HTTP_404_NOT_FOUND)

        enterprise_customer = enterprise_customer_user.enterprise_customer
        user = enterprise_customer_user.user_fk

        # Check if admin role assignment exists
        role_assignment = models.SystemWideEnterpriseUserRoleAssignment.objects.select_for_update().filter(
            user=user,
            enterprise_customer=enterprise_customer,
            role__name=ENTERPRISE_ADMIN_ROLE,
        )

        deleted_count, _ = role_assignment.delete()
        if deleted_count == 0:
            return self._error_response(
                'Admin role assignment not found',
                status.HTTP_404_NOT_FOUND
            )

        logger.info(
            "Deleted %d admin role assignment(s) for user %s in enterprise %s",
            deleted_count,
            user.id,
            enterprise_customer.uuid
        )

        # Check if user has other roles for this enterprise
        # No locking needed - we're only checking existence, and ECU is already locked
        has_other_roles_in_enterprise = models.SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user=user,
            enterprise_customer=enterprise_customer,
        ).exists()

        # Deactivate EnterpriseCustomerUser if no other roles exist in this enterprise (soft delete)
        user_deactivated = False
        if not has_other_roles_in_enterprise:
            # Set both active=False and linked=False to prevent signal from recreating roles
            enterprise_customer_user.active = False
            enterprise_customer_user.linked = False
            enterprise_customer_user.save(update_fields=['active', 'linked', 'modified'])
            logger.info(
                "Deactivated EnterpriseCustomerUser id=%s in enterprise %s (no other roles in this enterprise)",
                enterprise_customer_user.id,
                enterprise_customer.uuid
            )

            # Only deactivate global user account if user has NO access paths remaining
            has_systemwide_roles = models.SystemWideEnterpriseUserRoleAssignment.objects.filter(
                user=user,
            ).exists()

            # Check for other enterprise role constructs that may still grant access
            has_feature_roles = models.EnterpriseFeatureUserRoleAssignment.objects.filter(
                user=user,
            ).exists()

            # Check for Django-level privileged access
            has_django_privileged_access = bool(
                getattr(user, "is_staff", False) or getattr(user, "is_superuser", False)
            )

            has_any_access_paths = has_systemwide_roles or has_feature_roles or has_django_privileged_access

            if not has_any_access_paths:
                user.is_active = False
                user.save(update_fields=['is_active'])
                user_deactivated = True
                logger.info(
                    "Deactivated auth_user id=%s (no enterprise roles or privileged access)",
                    user.id
                )
            else:
                logger.info(
                    "Auth_user id=%s remains active (has enterprise roles or privileged access)",
                    user.id
                )
        else:
            logger.info(
                "EnterpriseCustomerUser id=%s active for user %s (has other roles in this enterprise)",
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
