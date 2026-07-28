"""
Tests for the `roles_api` module.
"""
import pytest

from django.core.cache import cache
from django.test import TestCase

from enterprise import roles_api
from enterprise.constants import (
    ENTERPRISE_ADMIN_ROLE,
    ENTERPRISE_LEARNER_ROLE,
    ENTERPRISE_OPERATOR_ROLE,
    SYSTEM_ENTERPRISE_CATALOG_ADMIN_ROLE,
    SYSTEM_ENTERPRISE_PROVISIONING_ADMIN_ROLE,
)
from enterprise.models import SystemWideEnterpriseRole, SystemWideEnterpriseUserRoleAssignment
from test_utils.factories import EnterpriseCustomerFactory, UserFactory


class TestUpdateRoleAssignmentsCommand(TestCase):
    """
    Tests the roles_api functions.
    """
    ALL_ROLE_NAMES = (
        ENTERPRISE_ADMIN_ROLE,
        ENTERPRISE_LEARNER_ROLE,
        ENTERPRISE_OPERATOR_ROLE,
        SYSTEM_ENTERPRISE_CATALOG_ADMIN_ROLE,
        SYSTEM_ENTERPRISE_PROVISIONING_ADMIN_ROLE
    )

    def setUp(self):
        """ Creates role objects for each system role specified in constants."""
        super().setUp()
        for role_name in self.ALL_ROLE_NAMES:
            SystemWideEnterpriseRole.objects.get_or_create(name=role_name)

    def tearDown(self):
        """ Delete any existing role objects."""
        super().tearDown()
        SystemWideEnterpriseRole.objects.all().delete()

    def test_roles_by_name(self):
        for role_name in self.ALL_ROLE_NAMES:
            role_object = roles_api.roles_by_name().get(role_name)
            self.assertEqual(role_name, role_object.name)


@pytest.mark.django_db
class TestAssignRole(TestCase):
    """Tests for ``roles_api.assign_role``."""

    def setUp(self):
        # The system-wide role getter is cache_memoize-cached; clear it so each
        # test resolves roles against its own transaction rather than a stale
        # (rolled-back) role object from a prior test.
        cache.clear()
        self.user = UserFactory()
        self.enterprise = EnterpriseCustomerFactory()
        super().setUp()

    def test_creates_all_contexts_assignment(self):
        """Creates an all-contexts assignment and reports created=True."""
        assignment, created = roles_api.assign_role(
            self.user,
            ENTERPRISE_OPERATOR_ROLE,
            applies_to_all_contexts=True,
        )
        assert created is True
        assert assignment.applies_to_all_contexts is True
        assert assignment.enterprise_customer is None
        assert assignment.role.name == ENTERPRISE_OPERATOR_ROLE

    def test_creates_customer_scoped_assignment(self):
        """Scopes the assignment to the given enterprise customer."""
        assignment, created = roles_api.assign_role(
            self.user,
            ENTERPRISE_ADMIN_ROLE,
            enterprise_customer=self.enterprise,
        )
        assert created is True
        assert assignment.enterprise_customer == self.enterprise
        assert assignment.applies_to_all_contexts is False

    def test_idempotent(self):
        """A repeat call returns the same row with created=False."""
        first, first_created = roles_api.assign_role(
            self.user,
            ENTERPRISE_OPERATOR_ROLE,
            applies_to_all_contexts=True,
        )
        second, second_created = roles_api.assign_role(
            self.user,
            ENTERPRISE_OPERATOR_ROLE,
            applies_to_all_contexts=True,
        )
        assert first_created is True
        assert second_created is False
        assert first.pk == second.pk
        assert SystemWideEnterpriseUserRoleAssignment.objects.filter(user=self.user).count() == 1

    def test_idempotent_ignores_applies_to_all_contexts_change(self):
        """A repeat call with a different ``applies_to_all_contexts`` returns the existing row.

        ``applies_to_all_contexts`` is not part of the unique key, so it must not
        participate in the lookup -- otherwise the second call would attempt a
        duplicate insert and raise IntegrityError.
        """
        first, first_created = roles_api.assign_role(
            self.user,
            ENTERPRISE_ADMIN_ROLE,
            enterprise_customer=self.enterprise,
            applies_to_all_contexts=False,
        )
        second, second_created = roles_api.assign_role(
            self.user,
            ENTERPRISE_ADMIN_ROLE,
            enterprise_customer=self.enterprise,
            applies_to_all_contexts=True,
        )
        assert first_created is True
        assert second_created is False
        assert first.pk == second.pk
        assert SystemWideEnterpriseUserRoleAssignment.objects.filter(user=self.user).count() == 1

    def test_creates_role_row_if_missing(self):
        """Creates the SystemWideEnterpriseRole row when it does not yet exist."""
        SystemWideEnterpriseRole.objects.filter(name=ENTERPRISE_OPERATOR_ROLE).delete()
        roles_api.assign_role(
            self.user,
            ENTERPRISE_OPERATOR_ROLE,
            applies_to_all_contexts=True,
        )
        assert SystemWideEnterpriseRole.objects.filter(name=ENTERPRISE_OPERATOR_ROLE).exists()

    def test_unknown_role_raises(self):
        """An unrecognised role name raises ``UnknownSystemWideRoleError``."""
        with pytest.raises(roles_api.UnknownSystemWideRoleError):
            roles_api.assign_role(self.user, 'bogus_role')
        assert not SystemWideEnterpriseUserRoleAssignment.objects.filter(user=self.user).exists()
