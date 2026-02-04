"""Tests for admin-related queryset helpers in enterprise managers."""

# pylint: disable=redefined-outer-name,unused-argument

import uuid
from datetime import timedelta
from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.contrib.sites.models import Site
from django.utils import timezone

from enterprise.constants import ENTERPRISE_ADMIN_ROLE
from enterprise.models import (
    EnterpriseCustomer,
    EnterpriseCustomerAdmin,
    EnterpriseCustomerUser,
    PendingEnterpriseCustomerAdminUser,
    SystemWideEnterpriseRole,
    SystemWideEnterpriseUserRoleAssignment,
)

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _unique_slug():
    return f"enterprise-{uuid.uuid4().hex[:8]}"


def _make_enterprise(site, name=None):
    return EnterpriseCustomer.objects.create(
        uuid=uuid.uuid4(),
        name=name or f"Test Enterprise {uuid.uuid4()}",
        slug=_unique_slug(),
        site=site,
    )


def _make_ecu(enterprise_customer, user):
    return EnterpriseCustomerUser.objects.create(
        enterprise_customer=enterprise_customer,
        user_id=user.id,
        user_fk=user,
    )


def _make_role_assignment(user, role, enterprise_customer):
    return SystemWideEnterpriseUserRoleAssignment.objects.create(
        user=user,
        role=role,
        enterprise_customer=enterprise_customer,
    )


def _make_enterprise_admin(enterprise_customer, user, role):
    """
    Creates the full chain needed for EnterpriseCustomerAdmin.objects.for_enterprise():
      1. EnterpriseCustomerUser
      2. SystemWideEnterpriseUserRoleAssignment  (enterprise_customer required)
      3. EnterpriseCustomerAdmin linked to the ECU

    Returns (ecu, admin) so tests can assert against either object's timestamps.
    """
    ecu = _make_ecu(enterprise_customer, user)
    _make_role_assignment(user, role, enterprise_customer)
    admin = EnterpriseCustomerAdmin.objects.create(enterprise_customer_user=ecu)
    return ecu, admin


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def site(db: None, settings):
    """Return a configured Django Site and required LMS settings for enterprise models."""

    settings.LMS_BASE = "lms.testserver"
    site_obj, _ = Site.objects.get_or_create(
        domain=settings.LMS_BASE,
        defaults={"name": "Test LMS"},
    )
    settings.SITE_ID = site_obj.id
    return site_obj


@pytest.fixture
def enterprise_customer(db: None, site: Site):
    return _make_enterprise(site)


@pytest.fixture
def other_enterprise_customer(db: None, site: Site):
    return _make_enterprise(site, name="Other Enterprise")


@pytest.fixture
def role_admin(db: None):
    role, _ = SystemWideEnterpriseRole.objects.get_or_create(name=ENTERPRISE_ADMIN_ROLE)
    return role


@pytest.fixture
def active_user(db: None):
    return User.objects.create_user(
        username="alice",
        email="alice@example.com",
        password="password",
        is_active=True,
    )


@pytest.fixture
def inactive_user(db: None):
    return User.objects.create_user(
        username="bob",
        email="bob@example.com",
        password="password",
        is_active=False,
    )


@pytest.fixture
def active_admin(
    db: None,
    enterprise_customer: EnterpriseCustomer,
    active_user: AbstractUser,
    role_admin: SystemWideEnterpriseRole,
):
    """
    Returns (ecu, admin) for the active admin user.
    Use ecu for ECU-level assertions, admin for joined_date assertions.
    """
    return _make_enterprise_admin(enterprise_customer, active_user, role_admin)


@pytest.fixture
def inactive_admin(
    db: None,
    enterprise_customer: EnterpriseCustomer,
    inactive_user: AbstractUser,
    role_admin: SystemWideEnterpriseRole,
):
    """Return (ecu, admin) tuple for an inactive admin user."""

    return _make_enterprise_admin(enterprise_customer, inactive_user, role_admin)


@pytest.fixture
def pending_admin(db: None, enterprise_customer: EnterpriseCustomer):
    return PendingEnterpriseCustomerAdminUser.objects.create(
        enterprise_customer=enterprise_customer,
        user_email="pending@example.com",
        created=timezone.now() - timedelta(days=1),
    )


# ---------------------------------------------------------------------------
# PendingEnterpriseCustomerAdminUser tests
# ---------------------------------------------------------------------------


def test_pending_for_enterprise_returns_pending_invites(
    db: None,
    enterprise_customer: EnterpriseCustomer,
    pending_admin: Any,
):
    qs = PendingEnterpriseCustomerAdminUser.objects.for_enterprise(enterprise_customer.uuid)
    row = qs.get()

    assert row["id"] == pending_admin.id
    assert row["email"] == "pending@example.com"
    assert row["name"] is None
    assert row["status"] == "Pending"
    assert row["joined_date"] is None
    assert row["invited_date"] == pending_admin.created


def test_pending_for_enterprise_excludes_other_enterprise(
    db: None,
    other_enterprise_customer: EnterpriseCustomer,
    pending_admin: Any,
):
    qs = PendingEnterpriseCustomerAdminUser.objects.for_enterprise(
        other_enterprise_customer.uuid
    )
    assert qs.count() == 0


def test_pending_for_enterprise_filters_by_user_query(
    db: None,
    enterprise_customer: EnterpriseCustomer,
    pending_admin: Any,
):
    qs = PendingEnterpriseCustomerAdminUser.objects.for_enterprise(
        enterprise_customer.uuid,
        user_query="pending@exam",
    )
    assert qs.count() == 1

    qs_empty = PendingEnterpriseCustomerAdminUser.objects.for_enterprise(
        enterprise_customer.uuid,
        user_query="nomatch",
    )
    assert qs_empty.count() == 0


def test_pending_for_enterprise_user_query_case_insensitive(
    db: None,
    enterprise_customer: EnterpriseCustomer,
    pending_admin: Any,
):
    qs = PendingEnterpriseCustomerAdminUser.objects.for_enterprise(
        enterprise_customer.uuid,
        user_query="PENDING@EXAMPLE",
    )
    assert qs.count() == 1


def test_pending_for_enterprise_no_user_query_returns_all(
    db: None,
    enterprise_customer: EnterpriseCustomer,
):
    PendingEnterpriseCustomerAdminUser.objects.create(
        enterprise_customer=enterprise_customer,
        user_email="a@example.com",
    )
    PendingEnterpriseCustomerAdminUser.objects.create(
        enterprise_customer=enterprise_customer,
        user_email="b@example.com",
    )
    qs = PendingEnterpriseCustomerAdminUser.objects.for_enterprise(enterprise_customer.uuid)
    assert qs.count() == 2


# ---------------------------------------------------------------------------
# EnterpriseCustomerAdmin tests
# ---------------------------------------------------------------------------


def test_admin_for_enterprise_includes_only_active_admins(
    db: None,
    active_admin: tuple,
):
    ecu, admin = active_admin
    qs = EnterpriseCustomerAdmin.objects.for_enterprise(ecu.enterprise_customer.uuid)

    assert qs.count() == 1
    row = qs.get()
    assert row["enterprise_customer_user_id"] == ecu.id
    assert row["email"] == ecu.user_fk.email
    assert row["name"] == ecu.user_fk.username
    assert row["status"] == "Admin"
    assert row["invited_date"] is None
    # joined_date maps to EnterpriseCustomerAdmin.created, NOT EnterpriseCustomerUser.created
    assert row["joined_date"] == admin.created


def test_admin_for_enterprise_excludes_other_enterprise(
    db: None,
    other_enterprise_customer: EnterpriseCustomer,
    active_admin: tuple,
):
    qs = EnterpriseCustomerAdmin.objects.for_enterprise(other_enterprise_customer.uuid)
    assert qs.count() == 0


def test_admin_for_enterprise_excludes_users_without_role(
    db: None,
    enterprise_customer: EnterpriseCustomer,
    active_user: AbstractUser,
):
    # ECU + EnterpriseCustomerAdmin row but NO role assignment
    ecu = _make_ecu(enterprise_customer, active_user)
    EnterpriseCustomerAdmin.objects.create(enterprise_customer_user=ecu)

    qs = EnterpriseCustomerAdmin.objects.for_enterprise(enterprise_customer.uuid)
    assert qs.count() == 0


def test_admin_for_enterprise_filters_by_user_query_username(
    db: None,
    active_admin: tuple,
):
    ecu, _ = active_admin
    qs = EnterpriseCustomerAdmin.objects.for_enterprise(
        ecu.enterprise_customer.uuid,
        user_query="ali",
    )
    assert qs.count() == 1

    qs_empty = EnterpriseCustomerAdmin.objects.for_enterprise(
        ecu.enterprise_customer.uuid,
        user_query="nomatch",
    )
    assert qs_empty.count() == 0


def test_admin_for_enterprise_filters_by_user_query_email(
    db: None,
    active_admin: tuple,
):
    ecu, _ = active_admin
    qs = EnterpriseCustomerAdmin.objects.for_enterprise(
        ecu.enterprise_customer.uuid,
        user_query="example.com",
    )
    assert qs.count() == 1


def test_admin_for_enterprise_user_query_case_insensitive(
    db: None,
    active_admin: tuple,
):
    ecu, _ = active_admin
    qs = EnterpriseCustomerAdmin.objects.for_enterprise(
        ecu.enterprise_customer.uuid,
        user_query="ALICE@EXAMPLE",
    )
    assert qs.count() == 1


def test_admin_for_enterprise_excludes_inactive_users(
    db: None,
    inactive_admin: tuple,
):
    ecu, _ = inactive_admin
    qs = EnterpriseCustomerAdmin.objects.for_enterprise(ecu.enterprise_customer.uuid)
    assert qs.count() == 0


def test_admin_for_enterprise_no_user_query_returns_all(
    db: None,
    enterprise_customer: EnterpriseCustomer,
    role_admin: SystemWideEnterpriseRole,
):
    user_a = User.objects.create_user(
        username="alice", email="alice@example.com", password="p", is_active=True
    )
    user_b = User.objects.create_user(
        username="carol", email="carol@example.com", password="p", is_active=True
    )
    for user in (user_a, user_b):
        _make_enterprise_admin(enterprise_customer, user, role_admin)

    qs = EnterpriseCustomerAdmin.objects.for_enterprise(enterprise_customer.uuid)
    assert qs.count() == 2
