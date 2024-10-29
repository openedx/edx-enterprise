"""
Rules needed to restrict access to the enterprise data api.
"""

import crum
import rules
from edx_rbac.utils import request_user_has_implicit_access_via_jwt, user_has_access_via_database
from edx_rest_framework_extensions.auth.jwt.authentication import get_decoded_jwt_from_auth
from edx_rest_framework_extensions.auth.jwt.cookies import get_decoded_jwt

from enterprise.constants import (
    DEFAULT_ENTERPRISE_ENROLLMENT_INTENTIONS_PERMISSION,
    DEFAULT_ENTERPRISE_ENROLLMENT_INTENTIONS_ROLE,
    ENTERPRISE_CATALOG_ADMIN_ROLE,
    ENTERPRISE_CUSTOMER_PROVISIONING_ADMIN_ACCESS_PERMISSION,
    ENTERPRISE_DASHBOARD_ADMIN_ROLE,
    ENTERPRISE_ENROLLMENT_API_ADMIN_ROLE,
    ENTERPRISE_FULFILLMENT_OPERATOR_ROLE,
    ENTERPRISE_REPORTING_CONFIG_ADMIN_ROLE,
    ENTERPRISE_SSO_ORCHESTRATOR_OPERATOR_ROLE,
    PENDING_ENT_CUSTOMER_ADMIN_PROVISIONING_ADMIN_ACCESS_PERMISSION,
    PROVISIONING_ENTERPRISE_CUSTOMER_ADMIN_ROLE,
    PROVISIONING_PENDING_ENTERPRISE_CUSTOMER_ADMIN_ROLE,
)
from enterprise.models import EnterpriseFeatureUserRoleAssignment


@rules.predicate
def has_implicit_access_to_sso_orchestration_configs(user, obj):  # pylint: disable=unused-argument
    """
    Check if a requesting user has implicit access to the `ENTERPRISE_SSO_ORCHESTRATOR_OPERATOR_ROLE` feature role.

    Params:
        user: An ``auth.User`` instance.
        obj: The string version of an ``EnterpriseCustomer.uuid``.

    Returns:
        boolean: whether the request user has access or not
    """
    request = crum.get_current_request()
    decoded_jwt = get_decoded_jwt(request) or get_decoded_jwt_from_auth(request)
    return request_user_has_implicit_access_via_jwt(decoded_jwt, ENTERPRISE_SSO_ORCHESTRATOR_OPERATOR_ROLE, obj)


@rules.predicate
def has_implicit_access_to_provisioning_enterprise_customers(user, obj):  # pylint: disable=unused-argument
    """
    Check if a requesting user has implicit access to the `PROVISIONING_ENTERPRISE_CUSTOMER_ADMIN_ROLE` feature role.

    Params:
        user: An ``auth.User`` instance.
        obj: The string version of an ``EnterpriseCustomer.uuid``.

    Returns:
        boolean: whether the request user has access or not
    """
    request = crum.get_current_request()
    decoded_jwt = get_decoded_jwt(request) or get_decoded_jwt_from_auth(request)
    return request_user_has_implicit_access_via_jwt(decoded_jwt, PROVISIONING_ENTERPRISE_CUSTOMER_ADMIN_ROLE, obj)


@rules.predicate
def has_implicit_access_to_provisioning_pending_enterprise_customer_admin_users(user, obj):  # pylint: disable=unused-argument
    """
    Check if a requesting user has implicit access to
    the `PROVISIONING_PENDING_ENTERPRISE_CUSTOMER_ADMIN_ROLE` feature role.

    Params:
        user: An ``auth.User`` instance.
        obj: The string version of an ``EnterpriseCustomer.uuid``.

    Returns:
        boolean: whether the request user has access or not
    """
    request = crum.get_current_request()
    decoded_jwt = get_decoded_jwt(request) or get_decoded_jwt_from_auth(request)
    return request_user_has_implicit_access_via_jwt(decoded_jwt,
                                                    PROVISIONING_PENDING_ENTERPRISE_CUSTOMER_ADMIN_ROLE,
                                                    obj)


@rules.predicate
def has_implicit_access_to_fulfillments(user, obj):  # pylint: disable=unused-argument
    """
    Check if a requesting user has implicit access to the `ENTERPRISE_FULFILLMENT_OPERATOR_ROLE` feature role.

    Params:
        user: An ``auth.User`` instance.
        obj: The string version of an ``EnterpriseCustomer.uuid``.

    Returns:
        boolean: whether the request user has access or not
    """
    request = crum.get_current_request()
    decoded_jwt = get_decoded_jwt(request) or get_decoded_jwt_from_auth(request)
    return request_user_has_implicit_access_via_jwt(decoded_jwt, ENTERPRISE_FULFILLMENT_OPERATOR_ROLE, obj)


@rules.predicate
def has_implicit_access_to_dashboard(user, obj):  # pylint: disable=unused-argument
    """
    Check that if request user has implicit access to `ENTERPRISE_DASHBOARD_ADMIN_ROLE` feature role.

    Params:
        user: An ``auth.User`` instance.
        obj: The string version of an ``EnterpriseCustomer.uuid``.

    Returns:
        boolean: whether the request user has access or not
    """
    request = crum.get_current_request()
    decoded_jwt = get_decoded_jwt(request) or get_decoded_jwt_from_auth(request)
    return request_user_has_implicit_access_via_jwt(decoded_jwt, ENTERPRISE_DASHBOARD_ADMIN_ROLE, obj)


@rules.predicate
def has_explicit_access_to_dashboard(user, obj):
    """
    Check that if request user has explicit access to `ENTERPRISE_DASHBOARD_ADMIN_ROLE` feature role.

    Params:
        user: An ``auth.User`` instance.
        obj: An ``EnterpriseCustomer`` instance.

    Returns:
        boolean: whether the request user has access or not
    """
    return user_has_access_via_database(
        user,
        ENTERPRISE_DASHBOARD_ADMIN_ROLE,
        EnterpriseFeatureUserRoleAssignment,
        obj,
    )


@rules.predicate
def has_implicit_access_to_catalog(user, obj):  # pylint: disable=unused-argument
    """
    Check that if request user has implicit access to `ENTERPRISE_CATALOG_ADMIN_ROLE` feature role.

    Params:
        user: An ``auth.User`` instance.
        obj: The string version of an ``EnterpriseCustomer.uuid``.

    Returns:
        boolean: whether the request user has access or not
    """
    request = crum.get_current_request()
    decoded_jwt = get_decoded_jwt(request) or get_decoded_jwt_from_auth(request)
    return request_user_has_implicit_access_via_jwt(decoded_jwt, ENTERPRISE_CATALOG_ADMIN_ROLE, obj)


@rules.predicate
def has_explicit_access_to_catalog(user, obj):
    """
    Check that if request user has explicit access to `ENTERPRISE_CATALOG_ADMIN_ROLE` feature role.

    Params:
        user: An ``auth.User`` instance.
        obj: An ``EnterpriseCustomer`` instance.

    Returns:
        boolean: whether the request user has access or not
    """
    return user_has_access_via_database(
        user,
        ENTERPRISE_CATALOG_ADMIN_ROLE,
        EnterpriseFeatureUserRoleAssignment,
        obj,
    )


@rules.predicate
def has_implicit_access_to_enrollment_api(user, obj):  # pylint: disable=unused-argument
    """
    Check that if request user has implicit access to `ENTERPRISE_ENROLLMENT_API_ADMIN_ROLE` feature role.

    Params:
        user: An ``auth.User`` instance.
        obj: The string version of an ``EnterpriseCustomer.uuid``.

    Returns:
        boolean: whether the request user has access or not
    """
    request = crum.get_current_request()
    decoded_jwt = get_decoded_jwt(request) or get_decoded_jwt_from_auth(request)
    return request_user_has_implicit_access_via_jwt(decoded_jwt, ENTERPRISE_ENROLLMENT_API_ADMIN_ROLE, obj)


@rules.predicate
def has_explicit_access_to_enrollment_api(user, obj):
    """
    Check that if request user has explicit access to `ENTERPRISE_ENROLLMENT_API_ADMIN_ROLE` feature role.

    Params:
        user: An ``auth.User`` instance.
        obj: An ``EnterpriseCustomer`` instance.

    Returns:
        boolean: whether the request user has access or not
    """
    return user_has_access_via_database(
        user,
        ENTERPRISE_ENROLLMENT_API_ADMIN_ROLE,
        EnterpriseFeatureUserRoleAssignment,
        obj,
    )


@rules.predicate
def has_implicit_access_to_reporting_api(user, obj):  # pylint: disable=unused-argument
    """
    Check that if request user has implicit access to `ENTERPRISE_REPORTING_CONFIG_ADMIN_ROLE` feature role.

    Params:
        user: An ``auth.User`` instance.
        obj: The string version of an ``EnterpriseCustomer.uuid``.

    Returns:
        boolean: whether the request user has access or not
    """
    request = crum.get_current_request()
    decoded_jwt = get_decoded_jwt(request) or get_decoded_jwt_from_auth(request)
    return request_user_has_implicit_access_via_jwt(decoded_jwt, ENTERPRISE_REPORTING_CONFIG_ADMIN_ROLE, obj)


@rules.predicate
def has_explicit_access_to_reporting_api(user, obj):
    """
    Check that if request user has explicit access to `ENTERPRISE_REPORTING_CONFIG_ADMIN_ROLE` feature role.

    Params:
        user: An ``auth.User`` instance.
        obj: An ``EnterpriseCustomer`` instance.

    Returns:
        boolean: whether the request user has access or not
    """
    return user_has_access_via_database(
        user,
        ENTERPRISE_REPORTING_CONFIG_ADMIN_ROLE,
        EnterpriseFeatureUserRoleAssignment,
        obj,
    )


@rules.predicate
def has_implicit_access_to_default_enterprise_enrollment_intentions(user, obj):  # pylint: disable=unused-argument
    """
    Check that if request user has implicit access to `ENTERPRISE_REPORTING_CONFIG_ADMIN_ROLE` feature role.

    Params:
        user: An ``auth.User`` instance.
        obj: The string version of an ``EnterpriseCustomer.uuid``.

    Returns:
        boolean: whether the request user has access or not
    """
    request = crum.get_current_request()
    decoded_jwt = get_decoded_jwt(request) or get_decoded_jwt_from_auth(request)
    return request_user_has_implicit_access_via_jwt(
        decoded_jwt,
        DEFAULT_ENTERPRISE_ENROLLMENT_INTENTIONS_ROLE,
        str(obj)
    )


rules.add_perm('enterprise.can_access_admin_dashboard',
               has_implicit_access_to_dashboard | has_explicit_access_to_dashboard)

rules.add_perm('enterprise.can_view_catalog',
               has_implicit_access_to_catalog | has_explicit_access_to_catalog)

rules.add_perm('enterprise.can_enroll_learners',
               has_implicit_access_to_enrollment_api | has_explicit_access_to_enrollment_api)

rules.add_perm('enterprise.can_manage_reporting_config',
               has_implicit_access_to_reporting_api | has_explicit_access_to_reporting_api)

rules.add_perm('enterprise.can_manage_enterprise_fulfillments', has_implicit_access_to_fulfillments)

rules.add_perm(
    'enterprise.can_manage_enterprise_orchestration_configs',
    has_implicit_access_to_sso_orchestration_configs,
)

rules.add_perm(
    ENTERPRISE_CUSTOMER_PROVISIONING_ADMIN_ACCESS_PERMISSION,
    has_implicit_access_to_provisioning_enterprise_customers,
)

rules.add_perm(
    PENDING_ENT_CUSTOMER_ADMIN_PROVISIONING_ADMIN_ACCESS_PERMISSION,
    has_implicit_access_to_provisioning_pending_enterprise_customer_admin_users,
)

rules.add_perm(
    DEFAULT_ENTERPRISE_ENROLLMENT_INTENTIONS_PERMISSION,
    has_implicit_access_to_default_enterprise_enrollment_intentions,
)
