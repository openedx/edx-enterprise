"""
Tests for the ``seed_enterprise_devstack_data`` management command.
"""

from unittest.mock import patch

import pytest

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from enterprise.constants import ENTERPRISE_ADMIN_ROLE, ENTERPRISE_LEARNER_ROLE
from enterprise.models import EnterpriseCustomer, EnterpriseCustomerUser

User = get_user_model()

GLOBAL_USERNAMES = {
    'enterprise_admin',
    'enterprise_openedx_operator',
    'license-manager_worker',
    'enterprise-catalog_worker',
    'enterprise_worker',
    'ecommerce_worker',
}


@patch('enterprise.devstack_api.UserProfile')
@pytest.mark.django_db
class TestSeedEnterpriseDevstackData(TestCase):
    """Tests for the seed_enterprise_devstack_data management command."""

    command = 'seed_enterprise_devstack_data'
    enterprise_name = 'Acme Corp'

    def _tenant_usernames(self, slug):
        """Return the set of tenant-scoped usernames the command creates for a slug."""
        return {
            f'{ENTERPRISE_LEARNER_ROLE}_{slug}',
            f'{ENTERPRISE_ADMIN_ROLE}_{slug}',
            f'{slug}_learner_1',
            f'{slug}_learner_2',
        }

    def test_default_links_only_tenant_scoped_users(self, _MockUserProfile):
        """Default run seeds global and tenant-scoped users, linking only the tenant-scoped ones."""
        call_command(self.command, enterprise_name=self.enterprise_name)

        enterprise_customer = EnterpriseCustomer.objects.get(name=self.enterprise_name)
        tenant_usernames = self._tenant_usernames(enterprise_customer.slug)

        # Both global and tenant-scoped users are created.
        assert User.objects.filter(username__in=GLOBAL_USERNAMES).count() == len(GLOBAL_USERNAMES)
        assert User.objects.filter(username__in=tenant_usernames).count() == len(tenant_usernames)

        # Only the tenant-scoped users are linked to this enterprise (Option C).
        linked_user_ids = set(
            EnterpriseCustomerUser.objects.filter(
                enterprise_customer=enterprise_customer,
            ).values_list('user_id', flat=True)
        )
        expected_user_ids = set(
            User.objects.filter(username__in=tenant_usernames).values_list('id', flat=True)
        )
        assert linked_user_ids == expected_user_ids

    def test_no_create_users_skips_all_users(self, _MockUserProfile):
        """``--no-create-users`` seeds the enterprise but creates no users or links."""
        call_command(self.command, enterprise_name=self.enterprise_name, no_create_users=True)

        enterprise_customer = EnterpriseCustomer.objects.get(name=self.enterprise_name)
        tenant_usernames = self._tenant_usernames(enterprise_customer.slug)

        assert not User.objects.filter(username__in=GLOBAL_USERNAMES).exists()
        assert not User.objects.filter(username__in=tenant_usernames).exists()
        assert not EnterpriseCustomerUser.objects.filter(
            enterprise_customer=enterprise_customer,
        ).exists()
