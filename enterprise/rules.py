"""
Rules needed to restrict access to the enterprise data api.
"""
from __future__ import absolute_import, unicode_literals

import rules
import waffle
from edx_rbac.utils import (
    get_decoded_jwt_from_request,
    get_request_or_stub,
    request_user_has_implicit_access_via_jwt,
    user_has_access_via_database,
)

from enterprise.constants import (
    ENTERPRISE_CATALOG_ADMIN_ROLE,
    ENTERPRISE_DASHBOARD_ADMIN_ROLE,
    ENTERPRISE_ENROLLMENT_API_ADMIN_ROLE,
    ENTERPRISE_ROLE_BASED_ACCESS_CONTROL_SWITCH,
)
from enterprise.models import EnterpriseFeatureUserRoleAssignment


@rules.predicate
def has_implicit_access_to_dashboard(user, obj):  # pylint: disable=unused-argument
    """
    Check that if request user has implicit access to `ENTERPRISE_DASHBOARD_ADMIN_ROLE` feature role.

    Returns:
        boolean: whether the request user has access or not
    """
    request = get_request_or_stub()
    decoded_jwt = get_decoded_jwt_from_request(request)
    return request_user_has_implicit_access_via_jwt(decoded_jwt, ENTERPRISE_DASHBOARD_ADMIN_ROLE)


@rules.predicate
def has_explicit_access_to_dashboard(user, obj):  # pylint: disable=unused-argument
    """
    Check that if request user has explicit access to `ENTERPRISE_DASHBOARD_ADMIN_ROLE` feature role.

    Returns:
        boolean: whether the request user has access or not
    """
    return user_has_access_via_database(
        user,
        ENTERPRISE_DASHBOARD_ADMIN_ROLE,
        EnterpriseFeatureUserRoleAssignment
    )


@rules.predicate
def has_implicit_access_to_catalog(user, obj):  # pylint: disable=unused-argument
    """
    Check that if request user has implicit access to `ENTERPRISE_CATALOG_ADMIN_ROLE` feature role.

    Returns:
        boolean: whether the request user has access or not
    """
    request = get_request_or_stub()
    decoded_jwt = get_decoded_jwt_from_request(request)
    return request_user_has_implicit_access_via_jwt(decoded_jwt, ENTERPRISE_CATALOG_ADMIN_ROLE, obj)


@rules.predicate
def has_explicit_access_to_catalog(user, obj):
    """
    Check that if request user has explicit access to `ENTERPRISE_CATALOG_ADMIN_ROLE` feature role.

    Returns:
        boolean: whether the request user has access or not
    """
    return user_has_access_via_database(
        user,
        ENTERPRISE_CATALOG_ADMIN_ROLE,
        EnterpriseFeatureUserRoleAssignment,
        obj
    )


@rules.predicate
def has_implicit_access_to_enrollment_api(user, obj):  # pylint: disable=unused-argument
    """
    Check that if request user has implicit access to `ENTERPRISE_ENROLLMENT_API_ADMIN_ROLE` feature role.

    Returns:
        boolean: whether the request user has access or not
    """
    request = get_request_or_stub()
    decoded_jwt = get_decoded_jwt_from_request(request)
    return request_user_has_implicit_access_via_jwt(decoded_jwt, ENTERPRISE_ENROLLMENT_API_ADMIN_ROLE, obj)


@rules.predicate
def has_explicit_access_to_enrollment_api(user, obj):
    """
    Check that if request user has explicit access to `ENTERPRISE_ENROLLMENT_API_ADMIN_ROLE` feature role.

    Returns:
        boolean: whether the request user has access or not
    """
    return user_has_access_via_database(
        user,
        ENTERPRISE_ENROLLMENT_API_ADMIN_ROLE,
        EnterpriseFeatureUserRoleAssignment,
        obj
    )


@rules.predicate
def rbac_permissions_disabled(user, obj):  # pylint: disable=unused-argument
    """
    Temporary check for rbac based permissions being enabled.
    """
    return not waffle.switch_is_active(ENTERPRISE_ROLE_BASED_ACCESS_CONTROL_SWITCH)


rules.add_perm('enterprise.can_access_admin_dashboard',
               rbac_permissions_disabled | has_implicit_access_to_dashboard | has_explicit_access_to_dashboard)

rules.add_perm('enterprise.can_view_catalog',
               rbac_permissions_disabled | has_implicit_access_to_catalog | has_explicit_access_to_catalog)

rules.add_perm('enterprise.can_enroll_learners',
               rbac_permissions_disabled | has_implicit_access_to_enrollment_api |
               has_explicit_access_to_enrollment_api)
