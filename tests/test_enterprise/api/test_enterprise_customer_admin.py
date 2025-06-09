"""
Tests for the `EnterpriseCustomerAdminViewSet`.
"""

from rest_framework import status
from rest_framework.test import APITestCase

from django.urls import reverse

from enterprise.models import EnterpriseCustomerAdmin
from test_utils.factories import (
    EnterpriseCustomerFactory,
    EnterpriseCustomerUserFactory,
    OnboardingFlowFactory,
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
