"""
Tests for the ``enterprise-admin-members`` API endpoint.
"""

from pytest import mark
from rest_framework import status

from django.conf import settings
from django.urls import reverse

from enterprise.constants import ENTERPRISE_ADMIN_ROLE
from test_utils import APITest
from test_utils.factories import (
    EnterpriseCustomerAdminFactory,
    EnterpriseCustomerFactory,
    EnterpriseCustomerUserFactory,
    PendingEnterpriseCustomerAdminUserFactory,
    UserFactory,
)


@mark.django_db
class TestEnterpriseAdminMembersViewSet(APITest):
    """
    Tests for EnterpriseAdminMembersViewSet.
    """

    def setUp(self):
        super().setUp()
        self.enterprise_customer = EnterpriseCustomerFactory()

        # Grant the test user the enterprise_admin role for this enterprise
        self.set_jwt_cookie(ENTERPRISE_ADMIN_ROLE, str(self.enterprise_customer.uuid))

        # Active admin
        self.admin_user = UserFactory(
            username='admin_jane',
            first_name='Jane',
            email='jane@example.com',
            is_active=True,
        )
        self.admin_ecu = EnterpriseCustomerUserFactory(
            user_id=self.admin_user.id,
            enterprise_customer=self.enterprise_customer,
        )
        self.admin_record = EnterpriseCustomerAdminFactory(
            enterprise_customer_user=self.admin_ecu,
        )

        # Pending admin
        self.pending_admin = PendingEnterpriseCustomerAdminUserFactory(
            enterprise_customer=self.enterprise_customer,
            user_email='pending@example.com',
        )

        self.url = settings.TEST_SERVER + reverse(
            'enterprise-admin-members',
            kwargs={'enterprise_uuid': str(self.enterprise_customer.uuid)},
        )

    # ── Permission tests ──────────────────────────────────────────────

    def test_unauthenticated_returns_401(self):
        """Unauthenticated request returns 401."""
        self.client.logout()
        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_user_without_admin_role_returns_403(self):
        """User without enterprise_admin role gets 403."""
        # Reset JWT to have no enterprise role
        self.set_jwt_cookie(system_wide_role='enterprise_learner', context='some_other_uuid')

        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json() == {'detail': 'Missing: enterprise.can_access_admin_dashboard'}

    def test_admin_for_different_enterprise_returns_403(self):
        """Admin of a different enterprise cannot access this enterprise's admins."""
        other_enterprise = EnterpriseCustomerFactory()
        self.set_jwt_cookie(ENTERPRISE_ADMIN_ROLE, str(other_enterprise.uuid))

        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    # ── List / field tests ────────────────────────────────────────────

    def test_list_returns_both_active_and_pending(self):
        """Active and pending admins appear in results."""
        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 2

        statuses = {r['status'] for r in response.data['results']}
        assert statuses == {'Admin', 'Pending'}

    def test_active_admin_fields(self):
        """Active admin record contains expected fields and values."""
        response = self.client.get(self.url)

        admin_result = next(r for r in response.data['results'] if r['status'] == 'Admin')
        assert admin_result['id'] == self.admin_ecu.id
        assert admin_result['name'] == 'Jane'
        assert admin_result['email'] == 'jane@example.com'
        assert admin_result['joined_date'] is not None
        assert admin_result['invited_date'] is None

    def test_pending_admin_fields(self):
        """Pending admin record contains expected fields and values."""
        response = self.client.get(self.url)

        pending_result = next(r for r in response.data['results'] if r['status'] == 'Pending')
        assert pending_result['id'] == self.pending_admin.id
        assert pending_result['name'] is None
        assert pending_result['email'] == 'pending@example.com'
        assert pending_result['invited_date'] is not None
        assert pending_result['joined_date'] is None

    def test_inactive_user_excluded(self):
        """Admin whose auth_user.is_active=False is not returned."""
        inactive_user = UserFactory(username='inactive_admin', is_active=False)
        inactive_ecu = EnterpriseCustomerUserFactory(
            user_id=inactive_user.id,
            enterprise_customer=self.enterprise_customer,
        )
        EnterpriseCustomerAdminFactory(enterprise_customer_user=inactive_ecu)

        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 2

    def test_scoped_to_enterprise(self):
        """Results are scoped to the given enterprise UUID."""
        other_enterprise = EnterpriseCustomerFactory()
        other_user = UserFactory(is_active=True)
        other_ecu = EnterpriseCustomerUserFactory(
            user_id=other_user.id,
            enterprise_customer=other_enterprise,
        )
        EnterpriseCustomerAdminFactory(enterprise_customer_user=other_ecu)

        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 2

    def test_empty_enterprise_returns_empty_results(self):
        """Enterprise with no admins returns empty list."""
        empty_enterprise = EnterpriseCustomerFactory()
        self.set_jwt_cookie(ENTERPRISE_ADMIN_ROLE, str(empty_enterprise.uuid))
        url = settings.TEST_SERVER + reverse(
            'enterprise-admin-members',
            kwargs={'enterprise_uuid': str(empty_enterprise.uuid)},
        )

        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 0
        assert response.data['results'] == []

    # ── Pagination tests ──────────────────────────────────────────────

    def test_pagination(self):
        """Results respect page_size query param."""
        response = self.client.get(self.url, {'page_size': 1})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
        assert response.data['count'] == 2

    # ── Filtering tests ───────────────────────────────────────────────

    def test_search_by_email(self):
        """user_query filters by email."""
        response = self.client.get(self.url, {'user_query': 'pending'})

        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 1
        assert response.data['results'][0]['email'] == 'pending@example.com'

    def test_search_by_name(self):
        """user_query filters active admins by name."""
        response = self.client.get(self.url, {'user_query': 'Jane'})

        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 1
        assert response.data['results'][0]['name'] == 'Jane'

    def test_search_no_matches_returns_empty(self):
        """user_query that matches nothing returns empty results."""
        response = self.client.get(self.url, {'user_query': 'nonexistent_user_xyz'})

        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 0
        assert response.data['results'] == []

    # ── Ordering tests ────────────────────────────────────────────────

    def test_default_ordering_is_by_name(self):
        """Without ?ordering= param, results are sorted by name ascending."""
        alpha_user = UserFactory(
            username='alpha_admin',
            first_name='Alpha',
            email='alpha@example.com',
            is_active=True,
        )
        alpha_ecu = EnterpriseCustomerUserFactory(
            user_id=alpha_user.id,
            enterprise_customer=self.enterprise_customer,
        )
        EnterpriseCustomerAdminFactory(enterprise_customer_user=alpha_ecu)

        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        names = [r['name'] for r in response.data['results']]
        # None (pending) sorts first, then Alpha, then Jane
        assert names == [None, 'Alpha', 'Jane']

    def test_ordering_by_email(self):
        """Results can be ordered by email ascending."""
        response = self.client.get(self.url, {'ordering': 'email'})

        assert response.status_code == status.HTTP_200_OK
        emails = [r['email'] for r in response.data['results']]
        assert emails == sorted(emails)

    def test_ordering_by_email_descending(self):
        """Results can be ordered by email descending."""
        response = self.client.get(self.url, {'ordering': '-email'})

        assert response.status_code == status.HTTP_200_OK
        emails = [r['email'] for r in response.data['results']]
        assert emails == sorted(emails, reverse=True)

    def test_ordering_by_status_ascending(self):
        """Results can be ordered by status ascending."""
        response = self.client.get(self.url, {'ordering': 'status'})

        assert response.status_code == status.HTTP_200_OK
        results = response.data['results']
        assert results[0]['status'] == 'Admin'
        assert results[1]['status'] == 'Pending'

    def test_ordering_by_status_descending(self):
        """Results can be ordered by status descending."""
        response = self.client.get(self.url, {'ordering': '-status'})

        assert response.status_code == status.HTTP_200_OK
        results = response.data['results']
        assert results[0]['status'] == 'Pending'
        assert results[1]['status'] == 'Admin'

    def test_invalid_ordering_field_uses_default(self):
        """Invalid ordering field is ignored; default ordering applies."""
        response = self.client.get(self.url, {'ordering': 'nonexistent_field'})

        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 2

    def test_search_and_ordering_combined(self):
        """user_query filtering works together with ordering."""
        bob_user = UserFactory(
            username='bob_admin',
            first_name='Bob',
            email='bob@example.com',
            is_active=True,
        )
        bob_ecu = EnterpriseCustomerUserFactory(
            user_id=bob_user.id,
            enterprise_customer=self.enterprise_customer,
        )
        EnterpriseCustomerAdminFactory(enterprise_customer_user=bob_ecu)

        response = self.client.get(self.url, {
            'user_query': 'example.com',
            'ordering': '-email',
        })

        assert response.status_code == status.HTTP_200_OK
        emails = [r['email'] for r in response.data['results']]
        assert emails == sorted(emails, reverse=True)
