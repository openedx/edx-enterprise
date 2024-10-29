"""
Tests for the `edx-enterprise` models module.
"""

from unittest import mock

import ddt
from pytest import mark

from enterprise.constants import (
    DEFAULT_ENTERPRISE_ENROLLMENT_INTENTIONS_PERMISSION,
    ENTERPRISE_ADMIN_ROLE,
    ENTERPRISE_CATALOG_ADMIN_ROLE,
    ENTERPRISE_DASHBOARD_ADMIN_ROLE,
    ENTERPRISE_ENROLLMENT_API_ADMIN_ROLE,
    ENTERPRISE_LEARNER_ROLE,
)
from enterprise.models import EnterpriseFeatureRole, EnterpriseFeatureUserRoleAssignment
from test_utils import TEST_UUID, APITest, factories


@mark.django_db()
@ddt.ddt
class TestEnterpriseRBACPermissions(APITest):
    """
    Test defined django rules for authorization checks.
    """

    @mock.patch('enterprise.rules.crum.get_current_request')
    @ddt.data(
        ('enterprise.can_access_admin_dashboard', ENTERPRISE_ADMIN_ROLE),
        ('enterprise.can_view_catalog', ENTERPRISE_ADMIN_ROLE),
        ('enterprise.can_enroll_learners', ENTERPRISE_ADMIN_ROLE),
        (DEFAULT_ENTERPRISE_ENROLLMENT_INTENTIONS_PERMISSION, ENTERPRISE_LEARNER_ROLE),
    )
    @ddt.unpack
    def test_has_implicit_access(self, permission, enterprise_role, get_current_request_mock):
        get_current_request_mock.return_value = self.get_request_with_jwt_cookie(enterprise_role, TEST_UUID)
        assert self.user.has_perm(permission, TEST_UUID)

    @mock.patch('enterprise.rules.crum.get_current_request')
    @ddt.data(
        ('enterprise.can_access_admin_dashboard', ENTERPRISE_DASHBOARD_ADMIN_ROLE),
        ('enterprise.can_view_catalog', ENTERPRISE_CATALOG_ADMIN_ROLE),
        ('enterprise.can_enroll_learners', ENTERPRISE_ENROLLMENT_API_ADMIN_ROLE),
    )
    @ddt.unpack
    def test_has_explicit_access(self, permission, feature_role, get_current_request_mock):
        get_current_request_mock.return_value = self.get_request_with_jwt_cookie()
        feature_role_object, __ = EnterpriseFeatureRole.objects.get_or_create(name=feature_role)
        enterprise_customer = factories.EnterpriseCustomerFactory(uuid=TEST_UUID)
        factories.EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=enterprise_customer
        )
        EnterpriseFeatureUserRoleAssignment.objects.create(user=self.user, role=feature_role_object)
        assert self.user.has_perm(permission, TEST_UUID)

    @mock.patch('enterprise.rules.crum.get_current_request')
    @ddt.data(
        'enterprise.can_access_admin_dashboard',
        'enterprise.can_view_catalog',
        'enterprise.can_enroll_learners',
    )
    def test_access_denied(self, permission, get_current_request_mock):
        get_current_request_mock.return_value = self.get_request_with_jwt_cookie()
        assert not self.user.has_perm(permission, TEST_UUID)
