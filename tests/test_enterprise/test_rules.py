# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` models module.
"""

from __future__ import absolute_import, unicode_literals, with_statement

import ddt
import mock
from pytest import mark
from waffle.models import Switch

from enterprise.constants import (
    ENTERPRISE_ADMIN_ROLE,
    ENTERPRISE_CATALOG_ADMIN_ROLE,
    ENTERPRISE_DASHBOARD_ADMIN_ROLE,
    ENTERPRISE_ENROLLMENT_API_ADMIN_ROLE,
    ENTERPRISE_OPERATOR_ROLE,
    ENTERPRISE_ROLE_BASED_ACCESS_CONTROL_SWITCH,
)
from enterprise.models import EnterpriseFeatureRole, EnterpriseFeatureUserRoleAssignment
from test_utils import TEST_UUID, APITest, factories


@mark.django_db()
@ddt.ddt
class TestEnterpriseRBACPermissions(APITest):
    """
    Test defined django rules for authorization checks.
    """

    @ddt.data(
        'enterprise.can_access_admin_dashboard',
        'enterprise.can_view_catalog',
        'enterprise.can_enroll_learners',
    )
    def test_permissions_rbac_disabled(self, permission):
        Switch.objects.update_or_create(name=ENTERPRISE_ROLE_BASED_ACCESS_CONTROL_SWITCH, defaults={'active': False})
        assert self.user.has_perm(permission, TEST_UUID)

    @mock.patch('enterprise.rules.get_request_or_stub')
    @ddt.data(
        'enterprise.can_access_admin_dashboard',
        'enterprise.can_view_catalog',
        'enterprise.can_enroll_learners',
    )
    def test_has_implicit_access(self, permission, get_request_or_stub_mock):
        Switch.objects.update_or_create(name=ENTERPRISE_ROLE_BASED_ACCESS_CONTROL_SWITCH, defaults={'active': True})
        get_request_or_stub_mock.return_value = self.get_request_with_jwt_cookie(ENTERPRISE_ADMIN_ROLE, TEST_UUID)
        assert self.user.has_perm(permission, TEST_UUID)

    @mock.patch('enterprise.rules.get_request_or_stub')
    @ddt.data(
        ('enterprise.can_access_admin_dashboard', ENTERPRISE_DASHBOARD_ADMIN_ROLE),
        ('enterprise.can_view_catalog', ENTERPRISE_CATALOG_ADMIN_ROLE),
        ('enterprise.can_enroll_learners', ENTERPRISE_ENROLLMENT_API_ADMIN_ROLE),
        ('enterprise.can_access_admin_dashboard', ENTERPRISE_OPERATOR_ROLE),
        ('enterprise.can_view_catalog', ENTERPRISE_OPERATOR_ROLE),
        ('enterprise.can_enroll_learners', ENTERPRISE_OPERATOR_ROLE),
    )
    @ddt.unpack
    def test_has_explicit_access(self, permission, feature_role, get_request_or_stub_mock):
        Switch.objects.update_or_create(name=ENTERPRISE_ROLE_BASED_ACCESS_CONTROL_SWITCH, defaults={'active': True})
        get_request_or_stub_mock.return_value = self.get_request_with_jwt_cookie()
        feature_role_object, __ = EnterpriseFeatureRole.objects.get_or_create(name=feature_role)
        enterprise_customer = factories.EnterpriseCustomerFactory(uuid=TEST_UUID)
        factories.EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=enterprise_customer
        )
        EnterpriseFeatureUserRoleAssignment.objects.create(user=self.user, role=feature_role_object)
        assert self.user.has_perm(permission, TEST_UUID)

    @mock.patch('enterprise.rules.get_request_or_stub')
    @ddt.data(
        'enterprise.can_access_admin_dashboard',
        'enterprise.can_view_catalog',
        'enterprise.can_enroll_learners',
    )
    def test_access_denied(self, permission, get_request_or_stub_mock):
        Switch.objects.update_or_create(name=ENTERPRISE_ROLE_BASED_ACCESS_CONTROL_SWITCH, defaults={'active': True})
        get_request_or_stub_mock.return_value = self.get_request_with_jwt_cookie()
        assert not self.user.has_perm(permission, TEST_UUID)
