"""
Tests for the `roles_api` module.
"""
from django.test import TestCase

from enterprise import roles_api
from enterprise.constants import (
    ENTERPRISE_ADMIN_ROLE,
    ENTERPRISE_LEARNER_ROLE,
    ENTERPRISE_OPERATOR_ROLE,
    SYSTEM_ENTERPRISE_CATALOG_ADMIN_ROLE,
    SYSTEM_ENTERPRISE_PROVISIONING_ADMIN_ROLE,
)
from enterprise.models import SystemWideEnterpriseRole


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
