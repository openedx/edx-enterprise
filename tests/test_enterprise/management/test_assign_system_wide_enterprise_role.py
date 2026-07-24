"""
Tests for the ``assign_system_wide_enterprise_role`` management command.
"""

import ddt
import pytest

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from enterprise.constants import ENTERPRISE_ADMIN_ROLE, ENTERPRISE_OPERATOR_ROLE
from enterprise.models import SystemWideEnterpriseUserRoleAssignment
from test_utils.factories import EnterpriseCustomerFactory, UserFactory

COMMAND = 'assign_system_wide_enterprise_role'


@ddt.ddt
@pytest.mark.django_db
class TestAssignSystemWideEnterpriseRole(TestCase):
    """Tests for the assign_system_wide_enterprise_role management command."""

    def setUp(self):
        self.user = UserFactory(username='enterprise_worker')
        self.enterprise = EnterpriseCustomerFactory()
        super().setUp()

    def test_all_contexts_assignment(self):
        """``--all-contexts`` creates an all-contexts assignment for the user."""
        call_command(COMMAND, username='enterprise_worker', role=ENTERPRISE_OPERATOR_ROLE, all_contexts=True)

        assignment = SystemWideEnterpriseUserRoleAssignment.objects.get(user=self.user)
        assert assignment.role.name == ENTERPRISE_OPERATOR_ROLE
        assert assignment.applies_to_all_contexts is True
        assert assignment.enterprise_customer is None

    @ddt.data(
        {'identifier_attr': 'slug'},
        {'identifier_attr': 'uuid'},
    )
    @ddt.unpack
    def test_customer_scoped(self, identifier_attr):
        """``--enterprise-customer`` resolves the customer by slug or UUID and scopes the assignment."""
        call_command(
            COMMAND,
            username='enterprise_worker',
            role=ENTERPRISE_ADMIN_ROLE,
            enterprise_customer=str(getattr(self.enterprise, identifier_attr)),
        )

        assignment = SystemWideEnterpriseUserRoleAssignment.objects.get(user=self.user)
        assert assignment.enterprise_customer == self.enterprise
        assert assignment.applies_to_all_contexts is False

    def test_idempotent(self):
        """Running twice does not create a duplicate assignment."""
        for _ in range(2):
            call_command(COMMAND, username='enterprise_worker', role=ENTERPRISE_OPERATOR_ROLE, all_contexts=True)

        assert SystemWideEnterpriseUserRoleAssignment.objects.filter(user=self.user).count() == 1

    def test_missing_user_raises(self):
        """A nonexistent username raises CommandError and creates nothing."""
        with pytest.raises(CommandError, match="User 'ghost' does not exist"):
            call_command(COMMAND, username='ghost', role=ENTERPRISE_OPERATOR_ROLE, all_contexts=True)
        assert not SystemWideEnterpriseUserRoleAssignment.objects.exists()

    def test_missing_customer_raises(self):
        """An unresolvable enterprise-customer identifier raises CommandError."""
        with pytest.raises(CommandError, match="does not exist"):
            call_command(
                COMMAND,
                username='enterprise_worker',
                role=ENTERPRISE_ADMIN_ROLE,
                enterprise_customer='no-such-slug',
            )

    def test_unrecognised_role_raises(self):
        """An unrecognised role name raises CommandError and creates nothing."""
        with pytest.raises(CommandError, match="not a recognised system-wide enterprise role"):
            call_command(COMMAND, username='enterprise_worker', role='bogus_role', all_contexts=True)
        assert not SystemWideEnterpriseUserRoleAssignment.objects.exists()
