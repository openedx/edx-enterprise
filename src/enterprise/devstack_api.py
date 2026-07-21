"""
Helper functions for devstack provisioning of enterprise test data.

These functions are composable building blocks used by management commands
(seed_enterprise_devstack_data, create_enterprise_linked_learner,
enroll_enterprise_learner) to set up enterprise fixtures in a local devstack
environment.  Each function is idempotent and operates on model instances
rather than string identifiers so that callers can compose them freely from
Python as well as from the CLI.
"""

import logging
from typing import Any

from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey

from django.contrib import auth
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.sites.models import Site
from django.db import transaction
from django.db.utils import IntegrityError
from django.utils.text import slugify

from consent.models import DataSharingConsent
from enterprise.constants import (
    ENTERPRISE_ADMIN_ROLE,
    ENTERPRISE_CATALOG_ADMIN_ROLE,
    ENTERPRISE_DASHBOARD_ADMIN_ROLE,
    ENTERPRISE_DATA_API_ACCESS_GROUP,
    ENTERPRISE_ENROLLMENT_API_ACCESS_GROUP,
    ENTERPRISE_ENROLLMENT_API_ADMIN_ROLE,
    ENTERPRISE_LEARNER_ROLE,
    ENTERPRISE_OPERATOR_ROLE,
    ENTERPRISE_REPORTING_CONFIG_ADMIN_ROLE,
)
from enterprise.models import (
    EnterpriseCourseEnrollment,
    EnterpriseCustomer,
    EnterpriseCustomerCatalog,
    EnterpriseCustomerUser,
    EnterpriseFeatureRole,
    EnterpriseFeatureUserRoleAssignment,
    SystemWideEnterpriseRole,
    SystemWideEnterpriseUserRoleAssignment,
)

try:
    from common.djangoapps.student.models import CourseEnrollment, UserProfile
except ImportError:
    CourseEnrollment = None
    UserProfile = None

LOGGER = logging.getLogger(__name__)
User = auth.get_user_model()
Group = auth.models.Group

CATALOG_CONTENT_FILTER = {'content_type': 'courserun'}


def get_or_create_site() -> Site:
    """
    Returns the default devstack site (example.com), creating it if needed.

    Returns:
        The Site instance for example.com.
    """
    site, _ = Site.objects.get_or_create(
        name='example.com',
        defaults={'domain': 'example.com'},
    )
    return site


def ensure_enterprise_groups() -> None:
    """Ensures the enterprise data API and enrollment API Django groups exist."""
    Group.objects.get_or_create(name=ENTERPRISE_DATA_API_ACCESS_GROUP)
    Group.objects.get_or_create(name=ENTERPRISE_ENROLLMENT_API_ACCESS_GROUP)


def get_or_create_enterprise_customer(name: str, site: Site | None = None) -> EnterpriseCustomer:
    """
    Returns an EnterpriseCustomer with the given name, creating it if needed.

    The created customer uses devstack-friendly defaults (both learner portal
    and data sharing consent enabled).

    Args:
        name: The name of the enterprise customer. The slug used for lookup
          and creation is derived from this via django.utils.text.slugify.
        site: An optional Site instance to associate with the customer.
          Passing it avoids an extra query when the caller already holds a
          Site instance. Defaults to the result of get_or_create_site().

    Returns:
        The existing or newly created EnterpriseCustomer instance.
    """
    if site is None:
        site = get_or_create_site()
    enterprise_customer, _ = EnterpriseCustomer.objects.get_or_create(
        slug=slugify(name),
        defaults={
            'name': name,
            'site': site,
            'country': 'US',
            'enable_learner_portal': True,
            'enable_data_sharing_consent': True,
            'enable_portal_code_management_screen': True,
            'enable_portal_reporting_config_screen': True,
            'enable_portal_saml_configuration_screen': True,
            'enable_portal_subscription_management_screen': True,
            'enable_portal_lms_configurations_screen': True,
        },
    )
    return enterprise_customer


def get_or_create_enterprise_catalog(enterprise_customer: EnterpriseCustomer) -> EnterpriseCustomerCatalog:
    """
    Returns an EnterpriseCustomerCatalog for the given customer, creating it if needed.

    Args:
        enterprise_customer: The EnterpriseCustomer that owns the catalog.

    Returns:
        The existing or newly created EnterpriseCustomerCatalog titled
        "All Course Runs" with a course-run-only content filter.
    """
    catalog, _ = EnterpriseCustomerCatalog.objects.get_or_create(
        title='All Course Runs',
        enterprise_customer=enterprise_customer,
        defaults={'content_filter': CATALOG_CONTENT_FILTER},
    )
    return catalog


def get_or_create_user(username: str, is_staff: bool = False) -> AbstractBaseUser:
    """
    Returns a User with the given username, creating it if needed.

    New users are created with email "{username}@example.com" and password
    "edx". A UserProfile row is also ensured when the platform UserProfile
    model is importable.

    Args:
        username: The username for the user to look up or create.
        is_staff: If True, the created user is marked as Django staff. Has
          no effect when the user already exists.

    Returns:
        The existing or newly created User instance.
    """
    try:
        with transaction.atomic():
            user = User.objects.create_user(
                username=username,
                email=f'{username}@example.com',
                password='edx',
                is_staff=is_staff,
            )
        LOGGER.info('Created user: %s', username)
    except IntegrityError:
        user = User.objects.get(username=username)
        LOGGER.info('Using existing user: %s', username)

    UserProfile.objects.update_or_create(
        user=user,
        defaults={'name': 'Test Enterprise User'},
    )

    return user


def get_or_create_enterprise_user(
    username: str,
    role: str,
    enterprise_customer: EnterpriseCustomer | None = None,
    applies_to_all_contexts: bool = False,
) -> dict[str, Any] | None:
    """
    Creates or retrieves a user with the given enterprise role.

    Adds the user to the appropriate Django groups and creates system-wide
    and feature role assignments.

    Args:
        username: The username for the user to look up or create.
        role: One of ENTERPRISE_LEARNER_ROLE, ENTERPRISE_ADMIN_ROLE, or
          ENTERPRISE_OPERATOR_ROLE. Any other value is treated as
          unrecognised and causes the function to return None.
        enterprise_customer: The EnterpriseCustomer to scope the role
          assignment to. Omit (or pass None) together with
          applies_to_all_contexts=True for operator/super-admin users.
        applies_to_all_contexts: If True, the system-wide role assignment
          applies across all enterprise contexts rather than the specific
          enterprise_customer.

    Returns:
        A dict with "user" and "role" keys describing the resulting
        assignment, or None if role is not one of the recognised values.
    """
    valid_roles = [ENTERPRISE_LEARNER_ROLE, ENTERPRISE_ADMIN_ROLE, ENTERPRISE_OPERATOR_ROLE]
    if role not in valid_roles:
        LOGGER.warning('User not created. Role %s not recognised.', role)
        return None

    is_staff = role == ENTERPRISE_OPERATOR_ROLE
    user = get_or_create_user(username, is_staff=is_staff)

    _add_user_to_groups(user, role)
    _create_system_wide_role_assignment(user, role, enterprise_customer, applies_to_all_contexts)
    _create_feature_role_assignments(user, role)

    return {'user': user, 'role': role}


def link_user_to_enterprise(
    user: AbstractBaseUser,
    enterprise_customer: EnterpriseCustomer,
    active: bool = True,
) -> tuple[EnterpriseCustomerUser, bool]:
    """
    Creates or updates an EnterpriseCustomerUser linking a user to an enterprise.

    Args:
        user: The User to link.
        enterprise_customer: The EnterpriseCustomer to link the user to.
        active: Whether the link should be marked active. Updates the
          active flag on an existing link.

    Returns:
        A tuple of (ecu, created) where ecu is the EnterpriseCustomerUser
        instance and created is True if it was created on this call.
    """
    ecu, created = EnterpriseCustomerUser.objects.update_or_create(
        user_id=user.pk,
        enterprise_customer=enterprise_customer,
        defaults={'active': active},
    )
    LOGGER.info(
        '%s EnterpriseCustomerUser: user=%s enterprise=%s active=%s',
        'Created' if created else 'Updated',
        user.username,
        enterprise_customer.name,
        active,
    )
    return ecu, created


def enroll_learner_in_course(
    user: AbstractBaseUser,
    course_id: str,
    enterprise_customer: EnterpriseCustomer,
    mode: str = 'audit',
    grant_dsc: bool = False,
) -> None:
    """
    Enrolls a user in a course under an enterprise customer.

    Creates (idempotently):
      - a platform CourseEnrollment
      - an EnterpriseCourseEnrollment
      - a DataSharingConsent record (granted=grant_dsc)

    Args:
        user: The User to enroll.
        course_id: The course-run key (e.g. "course-v1:edX+DemoX+Demo_Course").
        enterprise_customer: The EnterpriseCustomer that owns the
          subsidized enrollment.
        mode: The CourseEnrollment mode to use when creating the platform
          enrollment. Has no effect when the platform enrollment already
          exists.
        grant_dsc: Whether the DataSharingConsent record should be marked
          as granted.

    Raises:
        ValueError: course_id is not a valid course key.
        EnterpriseCustomerUser.DoesNotExist: user is not already linked to
            enterprise_customer. Callers must catch this and surface a
            friendlier message (e.g. by calling link_user_to_enterprise
            first, or by translating the exception at the CLI boundary).
    """
    try:
        course_key = CourseKey.from_string(course_id)
    except InvalidKeyError as exc:
        raise ValueError(f"Invalid course key: '{course_id}'.") from exc

    try:
        ecu = EnterpriseCustomerUser.objects.get(
            user_id=user.pk, enterprise_customer=enterprise_customer,
        )
    except EnterpriseCustomerUser.DoesNotExist:
        LOGGER.exception(
            "User '%s' is not linked to enterprise '%s'. "
            "Call link_user_to_enterprise first.",
            user.username, enterprise_customer.name,
        )
        raise

    enrollment, created = CourseEnrollment.objects.get_or_create(
        user=user,
        course_id=course_key,
        defaults={'mode': mode, 'is_active': True},
    )
    if not created and not enrollment.is_active:
        enrollment.activate()
    LOGGER.info(
        '%s CourseEnrollment: user=%s course=%s mode=%s',
        'Created' if created else 'Found existing', user.username, course_id, mode,
    )

    _, created = EnterpriseCourseEnrollment.objects.get_or_create(
        enterprise_customer_user=ecu,
        course_id=course_id,
    )
    LOGGER.info(
        '%s EnterpriseCourseEnrollment: user=%s course=%s enterprise=%s',
        'Created' if created else 'Found existing',
        user.username, course_id, enterprise_customer.name,
    )

    _, created = DataSharingConsent.objects.update_or_create(
        username=user.username,
        course_id=course_id,
        enterprise_customer=enterprise_customer,
        defaults={'granted': grant_dsc},
    )
    LOGGER.info(
        '%s DataSharingConsent: user=%s course=%s enterprise=%s granted=%s',
        'Created' if created else 'Updated',
        user.username, course_id, enterprise_customer.name, grant_dsc,
    )


# ---------------------------------------------------------------------------
# Internal helpers (not part of the public API)
# ---------------------------------------------------------------------------

def _add_user_to_groups(user: AbstractBaseUser, role: str) -> None:
    """Adds non-learner users to the enterprise data/enrollment API groups."""
    if role == ENTERPRISE_LEARNER_ROLE:
        return
    Group.objects.get(name=ENTERPRISE_DATA_API_ACCESS_GROUP).user_set.add(user)
    Group.objects.get(name=ENTERPRISE_ENROLLMENT_API_ACCESS_GROUP).user_set.add(user)


def _create_system_wide_role_assignment(
    user: AbstractBaseUser,
    role: str,
    enterprise_customer: EnterpriseCustomer | None,
    applies_to_all_contexts: bool,
) -> None:
    """Creates a system-wide role assignment if one does not already exist."""
    system_role, _ = SystemWideEnterpriseRole.objects.get_or_create(name=role)
    kwargs = {
        'user': user,
        'role': system_role,
        'applies_to_all_contexts': applies_to_all_contexts,
    }
    if enterprise_customer is not None:
        kwargs['enterprise_customer'] = enterprise_customer
    if not SystemWideEnterpriseUserRoleAssignment.objects.filter(**kwargs).exists():
        SystemWideEnterpriseUserRoleAssignment.objects.create(**kwargs)


def _create_feature_role_assignments(user: AbstractBaseUser, role: str) -> None:
    """Creates feature role assignments for admin/operator users."""
    if role == ENTERPRISE_LEARNER_ROLE:
        return
    feature_roles = [
        ENTERPRISE_CATALOG_ADMIN_ROLE,
        ENTERPRISE_DASHBOARD_ADMIN_ROLE,
        ENTERPRISE_ENROLLMENT_API_ADMIN_ROLE,
        ENTERPRISE_REPORTING_CONFIG_ADMIN_ROLE,
    ]
    for feature_role_name in feature_roles:
        feature_role, _ = EnterpriseFeatureRole.objects.get_or_create(name=feature_role_name)
        EnterpriseFeatureUserRoleAssignment.objects.get_or_create(user=user, role=feature_role)
