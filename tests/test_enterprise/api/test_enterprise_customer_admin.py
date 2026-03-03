
"""
Tests for EnterpriseCustomerAdmin API endpoints, including invite_admins.
"""
# --- Invite Admins Endpoint Tests ---

import ddt
from edx_rbac.constants import ALL_ACCESS_CONTEXT
from rest_framework import status
from rest_framework.test import APITestCase

from django.urls import reverse

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
                'customer_id': str(self.enterprise_customer_user.id),
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

    def test_delete_admin_invalid_role_parameter(self):
        """
        Test that DELETE request fails when role parameter is invalid.
        """
        self.set_jwt_cookie(SYSTEM_ENTERPRISE_PROVISIONING_ADMIN_ROLE, ALL_ACCESS_CONTEXT)
        response = self.client.delete(f'{self.delete_url}?role=invalid')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Invalid role', response.data['error'])

    def test_delete_admin_invalid_customer_id(self):
        """
        Test that DELETE request fails when customer_id is not a valid integer.
        """
        self.set_jwt_cookie(SYSTEM_ENTERPRISE_PROVISIONING_ADMIN_ROLE, ALL_ACCESS_CONTEXT)
        invalid_url = reverse(
            'enterprise-customer-admin-delete-admin',
            kwargs={'customer_id': 'not-an-integer'},
        )
        response = self.client.delete(f'{invalid_url}?role={ACTIVE_ADMIN_ROLE_TYPE}')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('customer_id must be a valid integer', response.data['error'])

    def test_soft_delete_success(self):
        """
        Test that DELETE with role=admin removes the admin role, deactivates the ECU
        (when no other roles), and returns 200.
        """
        self.set_jwt_cookie(SYSTEM_ENTERPRISE_PROVISIONING_ADMIN_ROLE, ALL_ACCESS_CONTEXT)

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

        # ECA record still exists in DB
        admin = EnterpriseCustomerAdmin.objects.get(pk=self.admin.pk)
        self.assertIsNotNone(admin)

        # ECU is deactivated
        self.enterprise_customer_user.refresh_from_db()
        self.assertFalse(self.enterprise_customer_user.active)

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

    def test_user_with_no_other_roles_ecu_deactivated(self):
        """
        Test that when a user has no other roles, the EnterpriseCustomerUser
        is deactivated after soft delete.
        """
        self.set_jwt_cookie(SYSTEM_ENTERPRISE_PROVISIONING_ADMIN_ROLE, ALL_ACCESS_CONTEXT)

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
                'customer_id': fake_id,
            },
        )

        response = self.client.delete(f'{url}?role={ACTIVE_ADMIN_ROLE_TYPE}')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_admin_enterprise_customer_not_found(self):
        """
        Test 404 when enterprise customer user does not exist.
        """
        self.set_jwt_cookie(SYSTEM_ENTERPRISE_PROVISIONING_ADMIN_ROLE, ALL_ACCESS_CONTEXT)

        fake_id = 999999
        url = reverse(
            'enterprise-customer-admin-delete-admin',
            kwargs={
                'customer_id': fake_id,
            },
        )

        response = self.client.delete(f'{url}?role={ACTIVE_ADMIN_ROLE_TYPE}')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        response = self.client.delete(f'{url}?role={ACTIVE_ADMIN_ROLE_TYPE}')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_admin_wrong_enterprise_customer(self):
        """
        Test 404 when trying to delete admin from different enterprise.
        """
        self.set_jwt_cookie(SYSTEM_ENTERPRISE_PROVISIONING_ADMIN_ROLE, ALL_ACCESS_CONTEXT)

        # Create admin for different enterprise
        other_enterprise = EnterpriseCustomerFactory()
        other_user = UserFactory(email='other@example.com')
        other_ecu = EnterpriseCustomerUserFactory(
            user_id=other_user.id,
            enterprise_customer=other_enterprise,
        )
        _other_admin = EnterpriseCustomerAdmin.objects.create(
            enterprise_customer_user=other_ecu,
        )
        # Assign admin role
        assign_admin_role(other_user, enterprise_customer=other_enterprise)

        url = reverse(
            'enterprise-customer-admin-delete-admin',
            kwargs={
                'customer_id': str(other_ecu.id),
            },
        )

        response = self.client.delete(f'{url}?role={ACTIVE_ADMIN_ROLE_TYPE}')

        # Should succeed - it's a valid admin from a different enterprise
        # The endpoint doesn't validate enterprise match when using ECU id
        self.assertEqual(response.status_code, status.HTTP_200_OK)

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
                'customer_id': str(pending_admin.id),
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
                'customer_id': fake_id,
            },
        )

        response = self.client.delete(f'{url}?role={PENDING_ADMIN_ROLE_TYPE}')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('Pending admin invitation not found', response.data['error'])

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
                'customer_id': str(pending_admin.id),
            },
        )

        response = self.client.delete(f'{url}?role={PENDING_ADMIN_ROLE_TYPE}')

        # Should succeed - pending admin ID is unique across all enterprises
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('other@example.com', response.data['message'])
        self.assertIn('deleted successfully', response.data['message'])

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
                'customer_id': str(pending_admin.id),
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
                'customer_id': str(pending_admin.id),
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
                'customer_id': str(pending_admin.id),
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
        self.admin_user = UserFactory(email='admin@example.com')
        self.enterprise_customer_user = EnterpriseCustomerUserFactory(
            user_id=self.admin_user.id,
            enterprise_customer=self.enterprise_customer
        )
        self.admin = EnterpriseCustomerAdmin.objects.create(
            enterprise_customer_user=self.enterprise_customer_user
        )
        self.invite_url = reverse(
            'enterprise-customer-admin-invite-admins',
            kwargs={'enterprise_customer_uuid': str(self.enterprise_customer.uuid)}
        )

    def set_jwt_admin(self):
        self.set_jwt_cookie(SYSTEM_ENTERPRISE_PROVISIONING_ADMIN_ROLE, ALL_ACCESS_CONTEXT)

    def test_invite_admins_success(self):
        self.set_jwt_admin()
        data = {'emails': ['newadmin@example.com']}
        response = self.client.post(self.invite_url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]['email'], 'newadmin@example.com')
        self.assertIn('status', response.data[0])

    def test_invite_admins_missing_emails(self):
        self.set_jwt_admin()
        data = {}
        response = self.client.post(self.invite_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['detail'], "The 'emails' field is required.")

    def test_invite_admins_empty_emails(self):
        self.set_jwt_admin()
        data = {'emails': []}
        response = self.client.post(self.invite_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(str(response.data['detail']), "The 'emails' field is required.")

    def test_invite_admins_duplicate_emails(self):
        self.set_jwt_admin()
        data = {'emails': ['dup@example.com', 'dup@example.com']}
        response = self.client.post(self.invite_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Duplicate emails are not allowed.', response.data['detail'])

    def test_invite_admins_permission_required(self):
        data = {'emails': ['noadmin@example.com']}
        response = self.client.post(self.invite_url, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_invite_admins_invalid_email_format(self):
        """Test that invalid email formats are rejected."""
        self.set_jwt_admin()
        data = {'emails': ['notanemail', 'valid@example.com']}
        response = self.client.post(self.invite_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # DRF's EmailField validator catches this and returns its own error
        self.assertIn('Enter a valid email address', str(response.data))

    def test_invite_admins_invalid_email_format_single(self):
        """Test that a single invalid email is rejected."""
        self.set_jwt_admin()
        data = {'emails': ['@example.com']}
        response = self.client.post(self.invite_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # DRF's EmailField validator catches this
        self.assertIn('Enter a valid email address', str(response.data))

    def test_invite_admins_case_insensitive(self):
        """Test that duplicate detection is case-insensitive."""
        self.set_jwt_admin()
        data = {'emails': ['Test@Example.com', 'test@example.com']}
        response = self.client.post(self.invite_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Duplicate emails are not allowed', str(response.data))

    def test_invite_admins_whitespace_handling(self):
        """Test that whitespace is properly stripped from emails."""
        self.set_jwt_admin()
        data = {'emails': ['  admin@test.com  ', 'admin2@test.com']}
        response = self.client.post(self.invite_url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Verify email was stripped and lowercased
        self.assertEqual(response.data[0]['email'], 'admin@test.com')

    def test_invite_admins_large_batch_accepted(self):
        """Test that large batches of emails are accepted."""
        self.set_jwt_admin()
        # Generate 100 emails to test large batch
        emails = [f'user{i}@example.com' for i in range(100)]
        data = {'emails': emails}
        response = self.client.post(self.invite_url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 100)

    def test_invite_admins_existing_admin_status(self):
        """Test that inviting an existing admin returns appropriate status."""
        self.set_jwt_admin()
        # admin@example.com is already an admin from setUp
        data = {'emails': ['admin@example.com', 'new@example.com']}
        response = self.client.post(self.invite_url, data)
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
        response1 = self.client.post(self.invite_url, {'emails': ['User@Example.COM']})
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        self.assertEqual(response1.data[0]['email'], 'user@example.com')
        self.assertEqual(response1.data[0]['status'], 'invite sent')

        # Second invite with different case should be recognized as already sent
        response2 = self.client.post(self.invite_url, {'emails': ['user@example.com']})
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertEqual(response2.data[0]['status'], 'already sent')
