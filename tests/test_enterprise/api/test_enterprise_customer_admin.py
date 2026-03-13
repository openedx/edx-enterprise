
"""
Tests for EnterpriseCustomerAdmin API endpoints, including invite_admins.
"""
# --- Invite Admins Endpoint Tests ---

from unittest import mock
from uuid import uuid4

import ddt
from edx_rbac.constants import ALL_ACCESS_CONTEXT
from rest_framework import status
from rest_framework.test import APIRequestFactory, APITestCase, force_authenticate

from django.db import DatabaseError
from django.urls import reverse

from enterprise.api.v1.views.enterprise_customer_admin import EnterpriseCustomerAdminViewSet
from enterprise.constants import (
    ACTIVE_ADMIN_ROLE_TYPE,
    ENTERPRISE_ADMIN_ROLE,
    ENTERPRISE_LEARNER_ROLE,
    ENTERPRISE_OPERATOR_ROLE,
    PENDING_ADMIN_ROLE_TYPE,
    SYSTEM_ENTERPRISE_CATALOG_ADMIN_ROLE,
    SYSTEM_ENTERPRISE_PROVISIONING_ADMIN_ROLE,
)
from enterprise.models import (
    EnterpriseCustomerAdmin,
    EnterpriseFeatureRole,
    EnterpriseFeatureUserRoleAssignment,
    PendingEnterpriseCustomerAdminUser,
    SystemWideEnterpriseUserRoleAssignment,
)
from enterprise.roles_api import assign_admin_role
from test_utils import APITest
from test_utils.factories import (
    EnterpriseCustomerFactory,
    EnterpriseCustomerUserFactory,
    OnboardingFlowFactory,
    PendingEnterpriseCustomerAdminUserFactory,
    UserFactory,
)


class TestEnterpriseCustomerAdminViewSet(APITestCase):
    """
    Tests for EnterpriseCustomerAdminViewSet.
    """
    def setUp(self):
        """Set up test data."""
        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)

        self.enterprise_customer = EnterpriseCustomerFactory()
        self.enterprise_customer_user = EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=self.enterprise_customer
        )

        self.admin = EnterpriseCustomerAdmin.objects.create(
            enterprise_customer_user=self.enterprise_customer_user
        )

        self.flow1 = OnboardingFlowFactory()
        self.flow2 = OnboardingFlowFactory()

        self.admin.completed_tour_flows.add(self.flow1)

        self.list_url = reverse('enterprise-customer-admin-list')
        self.detail_url = reverse('enterprise-customer-admin-detail', kwargs={'pk': self.admin.uuid})
        self.complete_tour_flow_url = reverse(
            'enterprise-customer-admin-complete-tour-flow',
            kwargs={'pk': self.admin.uuid}
        )
        self.create_admin_by_email_url = reverse('enterprise-customer-admin-create-admin-by-email')

    def test_get_list(self):
        """
        Test GET request to list endpoint.
        """
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)

        admin_data = response.data['results'][0]
        self.assertEqual(admin_data['uuid'], str(self.admin.uuid))
        self.assertEqual(admin_data['onboarding_tour_dismissed'], False)
        self.assertEqual(admin_data['onboarding_tour_completed'], False)
        self.assertEqual(len(admin_data['completed_tour_flows']), 1)
        self.assertEqual(admin_data['completed_tour_flows'][0], str(self.flow1.uuid))

    def test_complete_tour_flow_success(self):
        """
        Test successful completion of a tour flow.
        """
        data = {'flow_uuid': str(self.flow2.uuid)}
        response = self.client.post(self.complete_tour_flow_url, data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertIn(self.flow2.title, response.data['message'])

        self.admin.refresh_from_db()
        self.assertEqual(self.admin.completed_tour_flows.count(), 2)
        self.assertIn(self.flow2, self.admin.completed_tour_flows.all())

    def test_complete_tour_flow_missing_uuid(self):
        """
        Test completing a tour flow with missing UUID.
        """
        response = self.client.post(self.complete_tour_flow_url, {})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'flow_uuid is required')

    def test_unauthorized_access(self):
        """
        Test unauthorized access to endpoints.
        """
        other_user = UserFactory()
        self.client.force_authenticate(user=other_user)

        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 0)

        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        data = {'flow_uuid': str(self.flow2.uuid)}
        response = self.client.post(self.complete_tour_flow_url, data)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_method_not_allowed(self):
        """
        Test that POST to endpoint is not allowed.
        """
        data = {
            'enterprise_customer_user': self.enterprise_customer_user.id,
            'onboarding_tour_dismissed': False,
            'onboarding_tour_completed': False
        }
        response = self.client.post(self.list_url, data)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(response.data['detail'], 'Method "POST" not allowed.')

    def test_delete_method_not_allowed(self):
        """
        Test that DELETE to endpoint is not allowed.
        """
        response = self.client.delete(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(response.data['detail'], 'Method "DELETE" not allowed.')


@ddt.ddt
class TestCreateAdminByEmailEndpoint(APITest):
    """
    Tests for the create_admin_by_email endpoint.
    """
    def setUp(self):
        """Set up test data."""
        super().setUp()
        self.target_user = UserFactory(email='target@example.com')
        self.enterprise_customer = EnterpriseCustomerFactory()

        self.create_admin_by_email_url = reverse('enterprise-customer-admin-create-admin-by-email')

    def test_create_admin_by_email_success_new_admin(self):
        """
        Test successful creation of a new admin record.
        """
        self.set_jwt_cookie(SYSTEM_ENTERPRISE_PROVISIONING_ADMIN_ROLE, ALL_ACCESS_CONTEXT)

        data = {
            'email': self.target_user.email,
            'enterprise_customer_uuid': str(self.enterprise_customer.uuid)
        }

        response = self.client.post(self.create_admin_by_email_url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('uuid', response.data)

        # Verify EnterpriseCustomerAdmin was created
        self.assertTrue(
            EnterpriseCustomerAdmin.objects.filter(
                enterprise_customer_user__user_fk=self.target_user,
                enterprise_customer_user__enterprise_customer=self.enterprise_customer
            ).exists()
        )

        # Verify SystemWideEnterpriseUserRoleAssignment was created
        role_assignment = SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user=self.target_user,
            role__name=ENTERPRISE_ADMIN_ROLE,
            enterprise_customer=self.enterprise_customer
        )
        self.assertTrue(role_assignment.exists())

    def test_create_admin_by_email_success_existing_admin(self):
        """
        Test successful response when admin record already exists.
        """
        self.set_jwt_cookie(SYSTEM_ENTERPRISE_PROVISIONING_ADMIN_ROLE, ALL_ACCESS_CONTEXT)

        # Create existing admin record
        enterprise_customer_user = EnterpriseCustomerUserFactory(
            user_id=self.target_user.id,
            enterprise_customer=self.enterprise_customer
        )
        existing_admin = EnterpriseCustomerAdmin.objects.create(
            enterprise_customer_user=enterprise_customer_user
        )

        data = {
            'email': self.target_user.email,
            'enterprise_customer_uuid': str(self.enterprise_customer.uuid)
        }

        response = self.client.post(self.create_admin_by_email_url, data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['uuid'], str(existing_admin.uuid))

        # Verify SystemWideEnterpriseUserRoleAssignment was created
        role_assignment = SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user=self.target_user,
            role__name=ENTERPRISE_ADMIN_ROLE,
            enterprise_customer=self.enterprise_customer
        )
        self.assertTrue(role_assignment.exists())

    def test_create_admin_by_email_missing_email(self):
        """
        Test error response when email is missing.
        """
        self.set_jwt_cookie(SYSTEM_ENTERPRISE_PROVISIONING_ADMIN_ROLE, ALL_ACCESS_CONTEXT)

        data = {
            'enterprise_customer_uuid': str(self.enterprise_customer.uuid)
        }

        response = self.client.post(self.create_admin_by_email_url, data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'email is required')

    def test_create_admin_by_email_missing_enterprise_customer_uuid(self):
        """
        Test error response when enterprise_customer_uuid is missing.
        """
        self.set_jwt_cookie(SYSTEM_ENTERPRISE_PROVISIONING_ADMIN_ROLE, ALL_ACCESS_CONTEXT)

        data = {
            'email': self.target_user.email
        }

        response = self.client.post(self.create_admin_by_email_url, data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'enterprise_customer_uuid is required')

    def test_create_admin_by_email_user_not_found(self):
        """
        Test error response when user with email does not exist.
        """
        self.set_jwt_cookie(SYSTEM_ENTERPRISE_PROVISIONING_ADMIN_ROLE, ALL_ACCESS_CONTEXT)

        data = {
            'email': 'nonexistent@example.com',
            'enterprise_customer_uuid': str(self.enterprise_customer.uuid)
        }

        response = self.client.post(self.create_admin_by_email_url, data)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data['error'], 'User with email nonexistent@example.com does not exist')

    def test_create_admin_by_email_enterprise_customer_not_found(self):
        """
        Test error response when enterprise customer does not exist.
        """
        self.set_jwt_cookie(SYSTEM_ENTERPRISE_PROVISIONING_ADMIN_ROLE, ALL_ACCESS_CONTEXT)

        fake_uuid = '12345678-1234-5678-1234-567812345678'
        data = {
            'email': self.target_user.email,
            'enterprise_customer_uuid': fake_uuid
        }

        response = self.client.post(self.create_admin_by_email_url, data)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            response.data['error'],
            f'EnterpriseCustomer with uuid {fake_uuid} does not exist'
        )

    def test_create_admin_by_email_permission_required(self):
        """
        Test that the endpoint requires proper permissions.
        """
        # Don't set JWT cookie - should fail due to lack of permissions
        data = {
            'email': self.target_user.email,
            'enterprise_customer_uuid': str(self.enterprise_customer.uuid)
        }

        response = self.client.post(self.create_admin_by_email_url, data)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @ddt.data(
        ENTERPRISE_ADMIN_ROLE,
        ENTERPRISE_LEARNER_ROLE,
        ENTERPRISE_OPERATOR_ROLE,
        SYSTEM_ENTERPRISE_CATALOG_ADMIN_ROLE,
    )
    def test_create_admin_by_email_forbidden_roles(self, role):
        """
        Test that system-wide roles other than provisioning role are not allowed.
        """
        self.set_jwt_cookie(role, ALL_ACCESS_CONTEXT)

        data = {
            'email': self.target_user.email,
            'enterprise_customer_uuid': str(self.enterprise_customer.uuid)
        }

        response = self.client.post(self.create_admin_by_email_url, data)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


@ddt.ddt
class TestDeleteAdminEndpoint(APITest):
    """
    Tests for the delete_admin endpoint with role-based deletion.
    """
    def setUp(self):
        """Set up test data."""
        super().setUp()
        self.target_user = UserFactory(email='admin-target@example.com')
        self.enterprise_customer = EnterpriseCustomerFactory()
        self.enterprise_customer_user = EnterpriseCustomerUserFactory(
            user_id=self.target_user.id,
            enterprise_customer=self.enterprise_customer,
        )
        self.admin = EnterpriseCustomerAdmin.objects.create(
            enterprise_customer_user=self.enterprise_customer_user,
        )
        # Assign admin role
        assign_admin_role(self.target_user, enterprise_customer=self.enterprise_customer)

        self.delete_url = reverse(
            'enterprise-customer-admin-delete-admin',
            kwargs={
                'enterprise_customer_uuid': str(self.enterprise_customer.uuid),
                'id': str(self.enterprise_customer_user.id),
            },
        )
        self.list_url = reverse('enterprise-customer-admin-list')

    # --- Tests for role='admin' (active admin deletion) ---

    def test_delete_admin_missing_role_parameter(self):
        """
        Test that DELETE request fails when role parameter is missing.
        """
        self.set_jwt_cookie(SYSTEM_ENTERPRISE_PROVISIONING_ADMIN_ROLE, ALL_ACCESS_CONTEXT)
        response = self.client.delete(self.delete_url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('role parameter is required', response.data['error'])

    def test_delete_admin_missing_role_parameter_scoped_context(self):
        """
        Test missing role returns 400 (not 403) with enterprise-scoped provisioning context.
        """
        self.set_jwt_cookie(
            SYSTEM_ENTERPRISE_PROVISIONING_ADMIN_ROLE,
            str(self.enterprise_customer.uuid),
        )
        response = self.client.delete(self.delete_url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('role parameter is required', response.data['error'])

    def test_delete_admin_invalid_role_parameter(self):
        """
        Test that DELETE request fails when role parameter is invalid.
        """
        self.set_jwt_cookie(SYSTEM_ENTERPRISE_PROVISIONING_ADMIN_ROLE, ALL_ACCESS_CONTEXT)
        response = self.client.delete(f'{self.delete_url}?role=invalid')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Invalid role', response.data['error'])

    def test_delete_admin_invalid_id(self):
        """
        Test that DELETE request fails when id is not a valid integer.
        """
        self.set_jwt_cookie(SYSTEM_ENTERPRISE_PROVISIONING_ADMIN_ROLE, ALL_ACCESS_CONTEXT)
        invalid_url = reverse(
            'enterprise-customer-admin-delete-admin',
            kwargs={
                'enterprise_customer_uuid': str(self.enterprise_customer.uuid),
                'id': 'not-an-integer',
            },
        )
        response = self.client.delete(f'{invalid_url}?role={ACTIVE_ADMIN_ROLE_TYPE}')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('id must be a valid integer', response.data['error'])

    def test_soft_delete_success(self):
        """
        Test that DELETE with role=admin removes the admin role, deactivates the ECU
        (when no other roles), and returns 200.
        """
        self.set_jwt_cookie(SYSTEM_ENTERPRISE_PROVISIONING_ADMIN_ROLE, ALL_ACCESS_CONTEXT)

        self.target_user.is_active = True
        self.target_user.save(update_fields=['is_active'])

        # Remove auto-assigned learner role so ECU gets deactivated
        SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user=self.target_user,
            enterprise_customer=self.enterprise_customer,
        ).exclude(role__name=ENTERPRISE_ADMIN_ROLE).delete()

        response = self.client.delete(f'{self.delete_url}?role={ACTIVE_ADMIN_ROLE_TYPE}')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('admin-target@example.com', response.data['message'])
        self.assertIn('deleted successfully and user account deactivated', response.data['message'])
        self.assertIn('user_deactivated', response.data)
        self.assertTrue(response.data['user_deactivated'])

        # EnterpriseCustomerAdmin record still exists (soft delete via ECU deactivation).
        self.assertTrue(
            EnterpriseCustomerAdmin.objects.filter(pk=self.admin.pk).exists()
        )
        # ECA record still exists in DB
        admin = EnterpriseCustomerAdmin.objects.get(pk=self.admin.pk)
        self.assertIsNotNone(admin)

        # ECU is deactivated
        self.enterprise_customer_user.refresh_from_db()
        self.assertFalse(self.enterprise_customer_user.active)
        self.target_user.refresh_from_db()
        self.assertFalse(self.target_user.is_active)

        # Admin role is removed
        self.assertFalse(
            SystemWideEnterpriseUserRoleAssignment.objects.filter(
                user=self.target_user,
                role__name=ENTERPRISE_ADMIN_ROLE,
                enterprise_customer=self.enterprise_customer,
            ).exists()
        )

    def test_deleted_admin_excluded_from_list(self):
        """
        Test that soft-deleted admins are excluded from list API responses.
        """
        self.set_jwt_cookie(SYSTEM_ENTERPRISE_PROVISIONING_ADMIN_ROLE, ALL_ACCESS_CONTEXT)

        # Remove auto-assigned learner role so ECU gets deactivated on delete
        SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user=self.target_user,
            enterprise_customer=self.enterprise_customer,
        ).exclude(role__name=ENTERPRISE_ADMIN_ROLE).delete()

        # Soft delete the admin
        self.client.delete(f'{self.delete_url}?role={ACTIVE_ADMIN_ROLE_TYPE}')

        # Authenticate as the target user and check list
        self.client.force_authenticate(user=self.target_user)
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 0)

    def test_admin_role_removed(self):
        """
        Test that the enterprise_admin role is removed after soft delete.
        """
        self.set_jwt_cookie(SYSTEM_ENTERPRISE_PROVISIONING_ADMIN_ROLE, ALL_ACCESS_CONTEXT)

        # Verify role exists before delete
        self.assertTrue(
            SystemWideEnterpriseUserRoleAssignment.objects.filter(
                user=self.target_user,
                role__name=ENTERPRISE_ADMIN_ROLE,
                enterprise_customer=self.enterprise_customer,
            ).exists()
        )

        self.client.delete(f'{self.delete_url}?role={ACTIVE_ADMIN_ROLE_TYPE}')

        # Verify role no longer exists
        self.assertFalse(
            SystemWideEnterpriseUserRoleAssignment.objects.filter(
                user=self.target_user,
                role__name=ENTERPRISE_ADMIN_ROLE,
                enterprise_customer=self.enterprise_customer,
            ).exists()
        )

    def test_user_with_other_roles_ecu_stays_active(self):
        """
        Test that when a user has other roles (e.g., enterprise_learner),
        the EnterpriseCustomerUser remains active after soft delete.
        """
        self.set_jwt_cookie(SYSTEM_ENTERPRISE_PROVISIONING_ADMIN_ROLE, ALL_ACCESS_CONTEXT)
        initial_user_is_active = self.target_user.is_active

        # ECU creation via factory auto-assigns learner role via signal,
        # so the user already has enterprise_learner in addition to enterprise_admin.
        self.assertTrue(
            SystemWideEnterpriseUserRoleAssignment.objects.filter(
                user=self.target_user,
                enterprise_customer=self.enterprise_customer,
            ).exclude(role__name=ENTERPRISE_ADMIN_ROLE).exists()
        )

        response = self.client.delete(f'{self.delete_url}?role={ACTIVE_ADMIN_ROLE_TYPE}')

        # Verify response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('admin-target@example.com', response.data['message'])
        self.assertIn('deleted successfully', response.data['message'])
        self.assertFalse(response.data['user_deactivated'])

        # ECU should remain active because learner role still exists
        self.enterprise_customer_user.refresh_from_db()
        self.assertTrue(self.enterprise_customer_user.active)
        self.target_user.refresh_from_db()
        self.assertEqual(self.target_user.is_active, initial_user_is_active)

        # Admin model record still exists (not hard deleted).
        self.assertTrue(
            EnterpriseCustomerAdmin.objects.filter(pk=self.admin.pk).exists()
        )

    def test_user_with_no_other_roles_ecu_deactivated(self):
        """
        Test that when a user has no other roles, the EnterpriseCustomerUser
        is deactivated after soft delete.
        """
        self.set_jwt_cookie(SYSTEM_ENTERPRISE_PROVISIONING_ADMIN_ROLE, ALL_ACCESS_CONTEXT)

        self.target_user.is_active = True
        self.target_user.save(update_fields=['is_active'])

        # Remove the auto-assigned learner role so only admin role remains
        SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user=self.target_user,
            enterprise_customer=self.enterprise_customer,
        ).exclude(role__name=ENTERPRISE_ADMIN_ROLE).delete()

        # Confirm only admin role exists
        self.assertFalse(
            SystemWideEnterpriseUserRoleAssignment.objects.filter(
                user=self.target_user,
                enterprise_customer=self.enterprise_customer,
            ).exclude(role__name=ENTERPRISE_ADMIN_ROLE).exists()
        )

        response = self.client.delete(f'{self.delete_url}?role={ACTIVE_ADMIN_ROLE_TYPE}')

        # Verify response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('user_deactivated', response.data)
        self.assertTrue(response.data['user_deactivated'])

        # ECU should be deactivated
        self.enterprise_customer_user.refresh_from_db()
        self.assertFalse(self.enterprise_customer_user.active)
        self.target_user.refresh_from_db()
        self.assertFalse(self.target_user.is_active)

    def test_staff_user_account_not_deactivated(self):
        """
        Test that a staff user's account remains active even when their admin role is deleted.
        """
        self.set_jwt_cookie(SYSTEM_ENTERPRISE_PROVISIONING_ADMIN_ROLE, ALL_ACCESS_CONTEXT)

        # Set user as staff
        self.target_user.is_staff = True
        self.target_user.is_active = True
        self.target_user.save(update_fields=['is_staff', 'is_active'])

        # Remove learner role so only admin role remains
        SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user=self.target_user,
            enterprise_customer=self.enterprise_customer,
        ).exclude(role__name=ENTERPRISE_ADMIN_ROLE).delete()

        response = self.client.delete(f'{self.delete_url}?role={ACTIVE_ADMIN_ROLE_TYPE}')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('deleted successfully', response.data['message'])
        self.assertIn('user_deactivated', response.data)
        self.assertFalse(response.data['user_deactivated'])  # User account NOT deactivated

        # ECU should be deactivated
        self.enterprise_customer_user.refresh_from_db()
        self.assertFalse(self.enterprise_customer_user.active)

        # But user account should remain active due to staff status
        self.target_user.refresh_from_db()
        self.assertTrue(self.target_user.is_active)
        self.assertTrue(self.target_user.is_staff)

    def test_superuser_account_not_deactivated(self):
        """
        Test that a superuser's account remains active even when their admin role is deleted.
        """
        self.set_jwt_cookie(SYSTEM_ENTERPRISE_PROVISIONING_ADMIN_ROLE, ALL_ACCESS_CONTEXT)

        # Set user as superuser
        self.target_user.is_superuser = True
        self.target_user.is_active = True
        self.target_user.save(update_fields=['is_superuser', 'is_active'])

        # Remove learner role so only admin role remains
        SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user=self.target_user,
            enterprise_customer=self.enterprise_customer,
        ).exclude(role__name=ENTERPRISE_ADMIN_ROLE).delete()

        response = self.client.delete(f'{self.delete_url}?role={ACTIVE_ADMIN_ROLE_TYPE}')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('deleted successfully', response.data['message'])
        self.assertIn('user_deactivated', response.data)
        self.assertFalse(response.data['user_deactivated'])  # User account NOT deactivated

        # ECU should be deactivated
        self.enterprise_customer_user.refresh_from_db()
        self.assertFalse(self.enterprise_customer_user.active)

        # But user account should remain active due to superuser status
        self.target_user.refresh_from_db()
        self.assertTrue(self.target_user.is_active)
        self.assertTrue(self.target_user.is_superuser)

    def test_user_with_feature_roles_account_not_deactivated(self):
        """
        Test that a user with EnterpriseFeatureUserRoleAssignment remains active.
        """
        self.set_jwt_cookie(SYSTEM_ENTERPRISE_PROVISIONING_ADMIN_ROLE, ALL_ACCESS_CONTEXT)

        self.target_user.is_active = True
        self.target_user.save(update_fields=['is_active'])

        # Remove learner role so only admin role remains in SystemWide
        SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user=self.target_user,
            enterprise_customer=self.enterprise_customer,
        ).exclude(role__name=ENTERPRISE_ADMIN_ROLE).delete()

        # Add an EnterpriseFeatureUserRoleAssignment
        feature_role, _ = EnterpriseFeatureRole.objects.get_or_create(name='test_feature_role')
        EnterpriseFeatureUserRoleAssignment.objects.create(
            user=self.target_user,
            role=feature_role,
        )

        response = self.client.delete(f'{self.delete_url}?role={ACTIVE_ADMIN_ROLE_TYPE}')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('deleted successfully', response.data['message'])
        self.assertIn('user_deactivated', response.data)
        self.assertFalse(response.data['user_deactivated'])  # User account NOT deactivated

        # ECU should be deactivated
        self.enterprise_customer_user.refresh_from_db()
        self.assertFalse(self.enterprise_customer_user.active)

        # But user account should remain active due to feature role
        self.target_user.refresh_from_db()
        self.assertTrue(self.target_user.is_active)

    def test_delete_admin_permission_required(self):
        """
        Test that the endpoint requires the provisioning admin permission.
        """
        # Don't set JWT cookie
        response = self.client.delete(f'{self.delete_url}?role={ACTIVE_ADMIN_ROLE_TYPE}')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @ddt.data(
        ENTERPRISE_ADMIN_ROLE,
        ENTERPRISE_LEARNER_ROLE,
        ENTERPRISE_OPERATOR_ROLE,
        SYSTEM_ENTERPRISE_CATALOG_ADMIN_ROLE,
    )
    def test_delete_admin_forbidden_roles(self, role):
        """
        Test that roles other than provisioning admin cannot soft delete.
        """
        self.set_jwt_cookie(role, ALL_ACCESS_CONTEXT)

        response = self.client.delete(f'{self.delete_url}?role={ACTIVE_ADMIN_ROLE_TYPE}')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_admin_not_found(self):
        """
        Test 404 when admin record does not exist.
        """
        self.set_jwt_cookie(SYSTEM_ENTERPRISE_PROVISIONING_ADMIN_ROLE, ALL_ACCESS_CONTEXT)

        fake_id = 999999
        url = reverse(
            'enterprise-customer-admin-delete-admin',
            kwargs={
                'enterprise_customer_uuid': str(self.enterprise_customer.uuid),
                'id': fake_id,
            },
        )

        response = self.client.delete(f'{url}?role={ACTIVE_ADMIN_ROLE_TYPE}')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_admin_record_missing(self):
        """
        Test 404 when EnterpriseCustomerUser exists but admin record does not.
        """
        self.set_jwt_cookie(SYSTEM_ENTERPRISE_PROVISIONING_ADMIN_ROLE, ALL_ACCESS_CONTEXT)

        # Remove admin record but keep EnterpriseCustomerUser.
        self.admin.delete()

        response = self.client.delete(f'{self.delete_url}?role={ACTIVE_ADMIN_ROLE_TYPE}')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('Admin record not found', response.data['error'])

    def test_delete_admin_nonexistent_enterprise_uuid(self):
        """
        Test 404 when enterprise_customer_uuid does not map to an enterprise.
        """
        self.set_jwt_cookie(SYSTEM_ENTERPRISE_PROVISIONING_ADMIN_ROLE, ALL_ACCESS_CONTEXT)

        nonexistent_enterprise_uuid = str(uuid4())
        url = reverse(
            'enterprise-customer-admin-delete-admin',
            kwargs={
                'enterprise_customer_uuid': nonexistent_enterprise_uuid,
                'id': str(self.enterprise_customer_user.id),
            },
        )

        response = self.client.delete(f'{url}?role={ACTIVE_ADMIN_ROLE_TYPE}')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('detail', response.data)

    def test_delete_admin_invalid_enterprise_uuid_format(self):
        """
        Test 400 when enterprise_customer_uuid is malformed.
        """
        self.set_jwt_cookie(SYSTEM_ENTERPRISE_PROVISIONING_ADMIN_ROLE, ALL_ACCESS_CONTEXT)

        invalid_enterprise_uuid = '11111111-1111-1111-1111'
        url = reverse(
            'enterprise-customer-admin-delete-admin',
            kwargs={
                'enterprise_customer_uuid': invalid_enterprise_uuid,
                'id': str(self.enterprise_customer_user.id),
            },
        )

        response = self.client.delete(f'{url}?role={ACTIVE_ADMIN_ROLE_TYPE}')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('enterprise_customer_uuid must be a valid UUID', response.data['error'])

    def test_delete_admin_enterprise_customer_not_found(self):
        """
        Test 404 when enterprise customer user does not exist.
        """
        self.set_jwt_cookie(SYSTEM_ENTERPRISE_PROVISIONING_ADMIN_ROLE, ALL_ACCESS_CONTEXT)

        fake_id = 999999
        url = reverse(
            'enterprise-customer-admin-delete-admin',
            kwargs={
                'enterprise_customer_uuid': str(self.enterprise_customer.uuid),
                'id': fake_id,
            },
        )

        response = self.client.delete(f'{url}?role={ACTIVE_ADMIN_ROLE_TYPE}')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_admin_wrong_enterprise_customer(self):
        """
        Test that deleting an admin from a different enterprise via ECU id succeeds (200).
        """
        self.set_jwt_cookie(SYSTEM_ENTERPRISE_PROVISIONING_ADMIN_ROLE, ALL_ACCESS_CONTEXT)

        # Create admin for different enterprise
        other_enterprise = EnterpriseCustomerFactory()
        other_user = UserFactory(email='other@example.com', is_active=True)
        other_ecu = EnterpriseCustomerUserFactory(
            user_id=other_user.id,
            enterprise_customer=other_enterprise,
            active=True,
        )
        _other_admin = EnterpriseCustomerAdmin.objects.create(
            enterprise_customer_user=other_ecu,
        )
        # Assign admin role
        assign_admin_role(other_user, enterprise_customer=other_enterprise)

        url = reverse(
            'enterprise-customer-admin-delete-admin',
            kwargs={
                'enterprise_customer_uuid': str(other_enterprise.uuid),
                'id': str(other_ecu.id),
            },
        )

        response = self.client.delete(f'{url}?role={ACTIVE_ADMIN_ROLE_TYPE}')

        # Should succeed because URL enterprise UUID matches the ECU enterprise.
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_delete_admin_mismatched_enterprise_uuid_and_ecu_id(self):
        """
        Test 404 when enterprise_customer_uuid does not match the ECU's enterprise.
        """
        self.set_jwt_cookie(SYSTEM_ENTERPRISE_PROVISIONING_ADMIN_ROLE, ALL_ACCESS_CONTEXT)

        other_enterprise = EnterpriseCustomerFactory()
        mismatched_url = reverse(
            'enterprise-customer-admin-delete-admin',
            kwargs={
                'enterprise_customer_uuid': str(other_enterprise.uuid),
                'id': str(self.enterprise_customer_user.id),
            },
        )

        response = self.client.delete(f'{mismatched_url}?role={ACTIVE_ADMIN_ROLE_TYPE}')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('Admin user not found', response.data['error'])

    def test_delete_admin_no_role_assignment(self):
        """
        Test 404 when admin record exists but has no role assignment.
        """
        self.set_jwt_cookie(SYSTEM_ENTERPRISE_PROVISIONING_ADMIN_ROLE, ALL_ACCESS_CONTEXT)

        # Remove all role assignments
        SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user=self.target_user,
            enterprise_customer=self.enterprise_customer,
        ).delete()

        response = self.client.delete(f'{self.delete_url}?role={ACTIVE_ADMIN_ROLE_TYPE}')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('Admin role assignment not found', response.data['error'])

    def test_delete_admin_soft_deleted_ecu_not_processed(self):
        """
        Test 404 when EnterpriseCustomerUser is already soft deleted (inactive).
        """
        self.set_jwt_cookie(SYSTEM_ENTERPRISE_PROVISIONING_ADMIN_ROLE, ALL_ACCESS_CONTEXT)

        self.enterprise_customer_user.active = False
        self.enterprise_customer_user.save(update_fields=['active', 'modified'])

        response = self.client.delete(f'{self.delete_url}?role={ACTIVE_ADMIN_ROLE_TYPE}')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('Admin user not found', response.data['error'])

        # Ensure existing admin role assignment is untouched for inactive ECU path.
        self.assertTrue(
            SystemWideEnterpriseUserRoleAssignment.objects.filter(
                user=self.target_user,
                role__name=ENTERPRISE_ADMIN_ROLE,
                enterprise_customer=self.enterprise_customer,
            ).exists()
        )

    def test_delete_admin_case_insensitive_role(self):
        """
        Test that role parameter is case-insensitive.
        """
        self.set_jwt_cookie(SYSTEM_ENTERPRISE_PROVISIONING_ADMIN_ROLE, ALL_ACCESS_CONTEXT)

        # Remove auto-assigned learner role
        SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user=self.target_user,
            enterprise_customer=self.enterprise_customer,
        ).exclude(role__name=ENTERPRISE_ADMIN_ROLE).delete()

        response = self.client.delete(f'{self.delete_url}?role=ADMIN')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('admin-target@example.com', response.data['message'])
        self.assertIn('deleted successfully and user account deactivated', response.data['message'])
        self.assertTrue(response.data['user_deactivated'])

        # Verify admin role was removed
        self.assertFalse(
            SystemWideEnterpriseUserRoleAssignment.objects.filter(
                user=self.target_user,
                role__name=ENTERPRISE_ADMIN_ROLE,
                enterprise_customer=self.enterprise_customer,
            ).exists()
        )

    # --- Tests for role='pending' (pending admin deletion) ---

    def test_delete_pending_admin_success(self):
        """
        Test successful hard delete of a pending admin.
        """
        self.set_jwt_cookie(SYSTEM_ENTERPRISE_PROVISIONING_ADMIN_ROLE, ALL_ACCESS_CONTEXT)

        # Create a pending admin
        pending_admin = PendingEnterpriseCustomerAdminUserFactory(
            enterprise_customer=self.enterprise_customer,
            user_email='pending@example.com'
        )

        url = reverse(
            'enterprise-customer-admin-delete-admin',
            kwargs={
                'enterprise_customer_uuid': str(self.enterprise_customer.uuid),
                'id': str(pending_admin.id),
            },
        )

        response = self.client.delete(f'{url}?role={PENDING_ADMIN_ROLE_TYPE}')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('pending@example.com', response.data['message'])
        self.assertIn('Pending admin invitation', response.data['message'])
        self.assertIn('deleted successfully', response.data['message'])

        # Verify the pending admin was actually deleted
        self.assertFalse(
            PendingEnterpriseCustomerAdminUser.objects.filter(id=pending_admin.id).exists()
        )

    def test_delete_pending_admin_not_found(self):
        """
        Test 404 when pending admin does not exist.
        """
        self.set_jwt_cookie(SYSTEM_ENTERPRISE_PROVISIONING_ADMIN_ROLE, ALL_ACCESS_CONTEXT)

        fake_id = 999999
        url = reverse(
            'enterprise-customer-admin-delete-admin',
            kwargs={
                'enterprise_customer_uuid': str(self.enterprise_customer.uuid),
                'id': fake_id,
            },
        )

        response = self.client.delete(f'{url}?role={PENDING_ADMIN_ROLE_TYPE}')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('Pending admin invitation not found', response.data['error'])

    def test_delete_pending_admin_nonexistent_enterprise_uuid(self):
        """
        Test 404 when enterprise_customer_uuid does not map to an enterprise.
        """
        self.set_jwt_cookie(SYSTEM_ENTERPRISE_PROVISIONING_ADMIN_ROLE, ALL_ACCESS_CONTEXT)

        pending_admin = PendingEnterpriseCustomerAdminUserFactory(
            enterprise_customer=self.enterprise_customer,
            user_email='pending@example.com',
        )
        nonexistent_enterprise_uuid = str(uuid4())
        url = reverse(
            'enterprise-customer-admin-delete-admin',
            kwargs={
                'enterprise_customer_uuid': nonexistent_enterprise_uuid,
                'id': str(pending_admin.id),
            },
        )

        response = self.client.delete(f'{url}?role={PENDING_ADMIN_ROLE_TYPE}')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('detail', response.data)

    @mock.patch(
        'enterprise.api.v1.views.enterprise_customer_admin.'
        'models.PendingEnterpriseCustomerAdminUser.objects.select_for_update'
    )
    def test_delete_pending_admin_database_error(self, mock_select_for_update):
        """
        Test 500 when pending admin delete path raises DatabaseError.
        """
        self.set_jwt_cookie(SYSTEM_ENTERPRISE_PROVISIONING_ADMIN_ROLE, ALL_ACCESS_CONTEXT)

        pending_admin = PendingEnterpriseCustomerAdminUserFactory(
            enterprise_customer=self.enterprise_customer,
            user_email='pending@example.com'
        )
        url = reverse(
            'enterprise-customer-admin-delete-admin',
            kwargs={
                'enterprise_customer_uuid': str(self.enterprise_customer.uuid),
                'id': str(pending_admin.id),
            },
        )

        mock_select_for_update.return_value.select_related.return_value.get.side_effect = DatabaseError('db error')

        response = self.client.delete(f'{url}?role={PENDING_ADMIN_ROLE_TYPE}')

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn('Failed to delete pending admin invitation due to a database error', response.data['error'])

    @mock.patch(
        'enterprise.api.v1.views.enterprise_customer_admin.'
        'models.SystemWideEnterpriseUserRoleAssignment.objects.select_for_update'
    )
    def test_delete_active_admin_database_error(self, mock_select_for_update):
        """
        Test 500 when active admin delete path raises DatabaseError.
        """
        self.set_jwt_cookie(SYSTEM_ENTERPRISE_PROVISIONING_ADMIN_ROLE, ALL_ACCESS_CONTEXT)

        mock_role_assignment = mock.MagicMock()
        mock_role_assignment.delete.side_effect = DatabaseError('db error')
        mock_select_for_update.return_value.filter.return_value = mock_role_assignment

        response = self.client.delete(f'{self.delete_url}?role={ACTIVE_ADMIN_ROLE_TYPE}')

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn('Failed to delete admin due to a database error', response.data['error'])

    def test_delete_pending_admin_wrong_enterprise(self):
        """
        Test deleting pending admin from one enterprise doesn't affect another.
        """
        self.set_jwt_cookie(SYSTEM_ENTERPRISE_PROVISIONING_ADMIN_ROLE, ALL_ACCESS_CONTEXT)

        # Create pending admin for different enterprise
        other_enterprise = EnterpriseCustomerFactory()
        pending_admin = PendingEnterpriseCustomerAdminUserFactory(
            enterprise_customer=other_enterprise,
            user_email='other@example.com'
        )

        url = reverse(
            'enterprise-customer-admin-delete-admin',
            kwargs={
                'enterprise_customer_uuid': str(other_enterprise.uuid),
                'id': str(pending_admin.id),
            },
        )

        response = self.client.delete(f'{url}?role={PENDING_ADMIN_ROLE_TYPE}')

        # Should succeed - pending admin ID is unique across all enterprises
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('other@example.com', response.data['message'])
        self.assertIn('deleted successfully', response.data['message'])

    def test_delete_pending_admin_mismatched_enterprise_uuid_and_id(self):
        """
        Test 404 when enterprise_customer_uuid does not match pending admin enterprise.
        """
        self.set_jwt_cookie(SYSTEM_ENTERPRISE_PROVISIONING_ADMIN_ROLE, ALL_ACCESS_CONTEXT)

        pending_admin = PendingEnterpriseCustomerAdminUserFactory(
            enterprise_customer=self.enterprise_customer,
            user_email='pending@example.com',
        )
        other_enterprise = EnterpriseCustomerFactory()

        mismatched_url = reverse(
            'enterprise-customer-admin-delete-admin',
            kwargs={
                'enterprise_customer_uuid': str(other_enterprise.uuid),
                'id': str(pending_admin.id),
            },
        )

        response = self.client.delete(f'{mismatched_url}?role={PENDING_ADMIN_ROLE_TYPE}')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('Pending admin invitation not found', response.data['error'])

    def test_delete_pending_admin_permission_required(self):
        """
        Test that deleting pending admin requires proper permissions.
        """
        # Don't set JWT cookie
        pending_admin = PendingEnterpriseCustomerAdminUserFactory(
            enterprise_customer=self.enterprise_customer,
            user_email='pending@example.com'
        )

        url = reverse(
            'enterprise-customer-admin-delete-admin',
            kwargs={
                'enterprise_customer_uuid': str(self.enterprise_customer.uuid),
                'id': str(pending_admin.id),
            },
        )

        response = self.client.delete(f'{url}?role={PENDING_ADMIN_ROLE_TYPE}')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @ddt.data(
        ENTERPRISE_ADMIN_ROLE,
        ENTERPRISE_LEARNER_ROLE,
        ENTERPRISE_OPERATOR_ROLE,
        SYSTEM_ENTERPRISE_CATALOG_ADMIN_ROLE,
    )
    def test_delete_pending_admin_forbidden_roles(self, role):
        """
        Test that roles other than provisioning admin cannot delete pending admins.
        """
        self.set_jwt_cookie(role, ALL_ACCESS_CONTEXT)

        pending_admin = PendingEnterpriseCustomerAdminUserFactory(
            enterprise_customer=self.enterprise_customer,
            user_email='pending@example.com'
        )

        url = reverse(
            'enterprise-customer-admin-delete-admin',
            kwargs={
                'enterprise_customer_uuid': str(self.enterprise_customer.uuid),
                'id': str(pending_admin.id),
            },
        )

        response = self.client.delete(f'{url}?role={PENDING_ADMIN_ROLE_TYPE}')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_pending_admin_case_insensitive_role(self):
        """
        Test that role parameter is case-insensitive for pending deletion.
        """
        self.set_jwt_cookie(SYSTEM_ENTERPRISE_PROVISIONING_ADMIN_ROLE, ALL_ACCESS_CONTEXT)

        pending_admin = PendingEnterpriseCustomerAdminUserFactory(
            enterprise_customer=self.enterprise_customer,
            user_email='pending@example.com'
        )

        url = reverse(
            'enterprise-customer-admin-delete-admin',
            kwargs={
                'enterprise_customer_uuid': str(self.enterprise_customer.uuid),
                'id': str(pending_admin.id),
            },
        )

        response = self.client.delete(f'{url}?role=PENDING')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('pending@example.com', response.data['message'])
        self.assertIn('Pending admin invitation', response.data['message'])
        self.assertIn('deleted successfully', response.data['message'])

    def test_delete_with_role_in_body(self):
        """
        Test that role parameter can be sent in request body instead of query params.
        """
        self.set_jwt_cookie(SYSTEM_ENTERPRISE_PROVISIONING_ADMIN_ROLE, ALL_ACCESS_CONTEXT)

        # Remove auto-assigned learner role
        SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user=self.target_user,
            enterprise_customer=self.enterprise_customer,
        ).exclude(role__name=ENTERPRISE_ADMIN_ROLE).delete()

        response = self.client.delete(self.delete_url, data={'role': 'admin'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('admin-target@example.com', response.data['message'])
        self.assertIn('deleted successfully and user account deactivated', response.data['message'])
        self.assertTrue(response.data['user_deactivated'])


@ddt.ddt
class TestInviteAdminsEndpoint(APITest):
    """
    Tests for the invite_admins endpoint.
    """
    def setUp(self):
        super().setUp()
        self.enterprise_customer = EnterpriseCustomerFactory()
        self.admin_user = UserFactory(email='admin@example.com', is_active=True)
        self.enterprise_customer_user = EnterpriseCustomerUserFactory(
            user_id=self.admin_user.id,
            enterprise_customer=self.enterprise_customer
        )
        self.admin = EnterpriseCustomerAdmin.objects.create(
            enterprise_customer_user=self.enterprise_customer_user
        )
        # Assign admin role to make this a fully active admin
        assign_admin_role(self.admin_user, self.enterprise_customer)
        self.invite_url = reverse(
            'enterprise-customer-admin-admin-invites',
            kwargs={'enterprise_customer_uuid': str(self.enterprise_customer.uuid)}
        )
        self.request_factory = APIRequestFactory()
        self.invite_view = EnterpriseCustomerAdminViewSet.as_view({'post': 'invite_admins'})

    def _post_invite(self, data):
        request = self.request_factory.post(self.invite_url, data, format='json')
        force_authenticate(request, user=self.user)
        request.COOKIES.update({key: morsel.value for key, morsel in self.client.cookies.items()})
        return self.invite_view(
            request,
            enterprise_customer_uuid=str(self.enterprise_customer.uuid),
        )

    def set_jwt_admin(self):
        self.set_jwt_cookie(SYSTEM_ENTERPRISE_PROVISIONING_ADMIN_ROLE, ALL_ACCESS_CONTEXT)

    def test_invite_admins_success(self):
        self.set_jwt_admin()
        data = {'emails': ['newadmin@example.com']}
        response = self._post_invite(data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]['email'], 'newadmin@example.com')
        self.assertIn('status', response.data[0])

    def test_invite_admins_missing_emails(self):
        self.set_jwt_admin()
        data = {}
        response = self._post_invite(data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('emails', response.data)
        self.assertIn("The 'emails' field is required.", str(response.data['emails']))

    def test_invite_admins_empty_emails(self):
        self.set_jwt_admin()
        data = {'emails': []}
        response = self._post_invite(data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('emails', response.data)
        self.assertIn("This list may not be empty.", str(response.data['emails']))

    def test_invite_admins_duplicate_emails(self):
        self.set_jwt_admin()
        data = {'emails': ['dup@example.com', 'dup@example.com']}
        response = self._post_invite(data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Duplicate emails are not allowed.', str(response.data))

    def test_invite_admins_permission_required(self):
        data = {'emails': ['noadmin@example.com']}
        response = self._post_invite(data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_invite_admins_url_route_accepts_post(self):
        """Test invite URL resolves to POST invite action and does not return 405."""
        self.set_jwt_admin()
        response = self.client.post(self.invite_url, {'emails': ['routecheck@example.com']}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]['email'], 'routecheck@example.com')

    def test_invite_admins_invalid_enterprise_uuid_format(self):
        """Test malformed enterprise UUID returns a controlled 400 response."""
        self.set_jwt_admin()

        invalid_enterprise_uuid = '11111111-1111-1111-1111'
        request = self.request_factory.post(
            self.invite_url,
            {'emails': ['newadmin@example.com']},
            format='json',
        )
        force_authenticate(request, user=self.user)
        request.COOKIES.update({key: morsel.value for key, morsel in self.client.cookies.items()})

        response = self.invite_view(
            request,
            enterprise_customer_uuid=invalid_enterprise_uuid,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['detail'], 'enterprise_customer_uuid must be a valid UUID.')

    def test_invite_admins_invalid_email_format(self):
        """Test that invalid email formats are rejected."""
        self.set_jwt_admin()
        data = {'emails': ['notanemail', 'valid@example.com']}
        response = self._post_invite(data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # DRF's EmailField validator catches this and returns its own error
        self.assertIn('Enter a valid email address', str(response.data))
        self.assertNotIn('Invalid email format', str(response.data))

    def test_invite_admins_invalid_email_format_single(self):
        """Test that a single invalid email is rejected."""
        self.set_jwt_admin()
        data = {'emails': ['@example.com']}
        response = self._post_invite(data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # DRF's EmailField validator catches this
        self.assertIn('Enter a valid email address', str(response.data))
        self.assertNotIn('Invalid email format', str(response.data))

    def test_invite_admins_case_insensitive(self):
        """Test that duplicate detection is case-insensitive."""
        self.set_jwt_admin()
        data = {'emails': ['Test@Example.com', 'test@example.com']}
        response = self._post_invite(data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Duplicate emails are not allowed', str(response.data))

    def test_invite_admins_whitespace_handling(self):
        """Test that whitespace is properly stripped from emails."""
        self.set_jwt_admin()
        data = {'emails': ['  admin@test.com  ', 'admin2@test.com']}
        response = self._post_invite(data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Verify email was stripped and lowercased
        self.assertEqual(response.data[0]['email'], 'admin@test.com')

    def test_invite_admins_large_batch_accepted(self):
        """Test that large batches of emails are accepted."""
        self.set_jwt_admin()
        # Generate 100 emails to test large batch
        emails = [f'user{i}@example.com' for i in range(100)]
        data = {'emails': emails}
        response = self._post_invite(data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 100)

    @mock.patch('enterprise.api.v1.views.enterprise_customer_admin.admin_utils.create_pending_invites')
    def test_invite_admins_database_error_returns_500(self, mock_create_pending_invites):
        """Test that database errors when creating invites return a controlled 500 response."""
        self.set_jwt_admin()
        mock_create_pending_invites.side_effect = DatabaseError('db error')

        response = self._post_invite({'emails': ['newadmin@example.com']})

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(
            response.data['detail'],
            'Failed to create pending invites due to a database error.'
        )

    def test_invite_admins_existing_admin_status(self):
        """Test that inviting an existing admin returns appropriate status."""
        self.set_jwt_admin()
        # admin@example.com is already an admin from setUp
        data = {'emails': ['admin@example.com', 'new@example.com']}
        response = self._post_invite(data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check that existing admin is recognized
        admin_response = [r for r in response.data if r['email'] == 'admin@example.com'][0]
        self.assertEqual(admin_response['status'], 'already admin')
        # Check that new email gets invite status
        new_response = [r for r in response.data if r['email'] == 'new@example.com'][0]
        self.assertEqual(new_response['status'], 'invite sent')

    def test_invite_admins_mixed_case_normalization(self):
        """Test that email case is normalized consistently."""
        self.set_jwt_admin()
        # First invite with mixed case
        response1 = self._post_invite({'emails': ['User@Example.COM']})
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        self.assertEqual(response1.data[0]['email'], 'user@example.com')
        self.assertEqual(response1.data[0]['status'], 'invite sent')

        # Second invite with different case should be recognized as already sent
        response2 = self._post_invite({'emails': ['user@example.com']})
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertEqual(response2.data[0]['status'], 'already sent')

    @mock.patch('enterprise.api.v1.views.enterprise_customer_admin.admin_utils.create_pending_invites')
    def test_invite_admins_race_condition_handling(self, mock_create_pending_invites):
        """Test that race conditions in invite creation are handled correctly."""
        self.set_jwt_admin()

        # Simulate race condition: tried to create 2 invites, but one already existed
        # (get_or_create found existing record for 'race@example.com')
        mock_invite_new = mock.Mock()
        mock_invite_new.user_email = 'new@example.com'

        mock_create_pending_invites.return_value = [mock_invite_new]

        # Request to invite both emails
        data = {'emails': ['new@example.com', 'race@example.com']}
        response = self._post_invite(data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

        # The email that was actually created should show 'invite sent'
        new_response = [r for r in response.data if r['email'] == 'new@example.com'][0]
        self.assertEqual(new_response['status'], 'invite sent')

        # The email that hit race condition should show 'already sent'
        race_response = [r for r in response.data if r['email'] == 'race@example.com'][0]
        self.assertEqual(race_response['status'], 'already sent')

    def test_invite_admins_mixed_statuses(self):
        """Test inviting multiple admins with different statuses in one request."""
        self.set_jwt_admin()

        # Create pending invite
        PendingEnterpriseCustomerAdminUserFactory(
            enterprise_customer=self.enterprise_customer,
            user_email='pending@example.com'
        )

        # admin@example.com already exists from setUp with proper role
        # Assign role to existing admin
        assign_admin_role(self.admin_user, self.enterprise_customer)

        # Invite all types
        data = {'emails': [
            'admin@example.com',       # existing admin
            'pending@example.com',     # already pending
            'new@example.com'          # new invite
        ]}
        response = self._post_invite(data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)

        # Check each status
        status_map = {item['email']: item['status'] for item in response.data}
        self.assertEqual(status_map['admin@example.com'], 'already admin')
        self.assertEqual(status_map['pending@example.com'], 'already sent')
        self.assertEqual(status_map['new@example.com'], 'invite sent')

        # Only new invite should create pending record
        self.assertTrue(
            PendingEnterpriseCustomerAdminUser.objects.filter(
                user_email='new@example.com'
            ).exists()
        )

    @mock.patch('enterprise.api.v1.views.enterprise_customer_admin.admin_utils.get_existing_admin_emails')
    def test_invite_admins_database_error_fetching_status_returns_500(self, mock_get_existing_admin_emails):
        """Test that database errors when fetching admin status return 500."""
        self.set_jwt_admin()
        mock_get_existing_admin_emails.side_effect = DatabaseError("Database connection failed")

        data = {'emails': ['test@example.com']}
        response = self._post_invite(data)

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn('detail', response.data)
        self.assertEqual(
            response.data['detail'],
            'Failed to retrieve admin information due to a database error.'
        )
