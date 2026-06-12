"""
Tests for the devstack-only helpers in ``enterprise/devstack_api.py``.
"""

from unittest.mock import MagicMock, patch

import ddt
import pytest

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.sites.models import Site
from django.test import TestCase

from consent.models import DataSharingConsent
from enterprise.constants import (
    ENTERPRISE_ADMIN_ROLE,
    ENTERPRISE_DATA_API_ACCESS_GROUP,
    ENTERPRISE_ENROLLMENT_API_ACCESS_GROUP,
    ENTERPRISE_LEARNER_ROLE,
    ENTERPRISE_OPERATOR_ROLE,
)
from enterprise.devstack_api import (
    enroll_learner_in_course,
    ensure_enterprise_groups,
    get_or_create_enterprise_catalog,
    get_or_create_enterprise_customer,
    get_or_create_enterprise_user,
    get_or_create_site,
    get_or_create_user,
    link_user_to_enterprise,
)
from enterprise.models import (
    EnterpriseCourseEnrollment,
    EnterpriseCustomer,
    EnterpriseCustomerCatalog,
    EnterpriseCustomerUser,
    EnterpriseFeatureUserRoleAssignment,
    SystemWideEnterpriseUserRoleAssignment,
)
from test_utils.factories import EnterpriseCustomerFactory, UserFactory

User = get_user_model()


@pytest.mark.django_db
class TestGetOrCreateSite(TestCase):
    """Tests for ``get_or_create_site``."""

    def test_creates_site(self):
        """Creates the default ``example.com`` site when none exists."""
        Site.objects.all().delete()
        site = get_or_create_site()
        assert site.name == 'example.com'
        assert site.domain == 'example.com'

    def test_idempotent(self):
        """Repeated calls do not create duplicate Site rows."""
        get_or_create_site()
        get_or_create_site()
        assert Site.objects.filter(name='example.com').count() == 1


@pytest.mark.django_db
class TestEnsureEnterpriseGroups(TestCase):
    """Tests for ``ensure_enterprise_groups``."""

    def test_creates_groups(self):
        """Creates both enterprise API access Groups when missing."""
        Group.objects.filter(name__in=[
            ENTERPRISE_DATA_API_ACCESS_GROUP,
            ENTERPRISE_ENROLLMENT_API_ACCESS_GROUP,
        ]).delete()
        ensure_enterprise_groups()
        assert Group.objects.filter(name=ENTERPRISE_DATA_API_ACCESS_GROUP).exists()
        assert Group.objects.filter(name=ENTERPRISE_ENROLLMENT_API_ACCESS_GROUP).exists()

    def test_idempotent(self):
        """Repeated calls do not create duplicate Group rows."""
        ensure_enterprise_groups()
        ensure_enterprise_groups()
        assert Group.objects.filter(name=ENTERPRISE_DATA_API_ACCESS_GROUP).count() == 1


@pytest.mark.django_db
class TestGetOrCreateEnterpriseCustomer(TestCase):
    """Tests for ``get_or_create_enterprise_customer``."""

    def test_creates_customer(self):
        """Creates an EnterpriseCustomer with learner portal and DSC enabled."""
        site = get_or_create_site()
        customer = get_or_create_enterprise_customer(name='Acme Corp', site=site)
        assert customer.name == 'Acme Corp'
        assert customer.enable_learner_portal is True
        assert customer.enable_data_sharing_consent is True

    def test_creates_site_if_none(self):
        """Falls back to creating a default Site when no site is passed in."""
        customer = get_or_create_enterprise_customer(name='Acme Corp')
        assert customer.name == 'Acme Corp'

    def test_idempotent(self):
        """Repeated calls do not create duplicate EnterpriseCustomer rows."""
        get_or_create_enterprise_customer(name='Acme Corp')
        get_or_create_enterprise_customer(name='Acme Corp')
        assert EnterpriseCustomer.objects.filter(name='Acme Corp').count() == 1


@pytest.mark.django_db
class TestGetOrCreateEnterpriseCatalog(TestCase):
    """Tests for ``get_or_create_enterprise_catalog``."""

    def test_creates_catalog(self):
        """Creates the default ``All Course Runs`` catalog for the given customer."""
        customer = EnterpriseCustomerFactory(name='Acme Corp')
        catalog = get_or_create_enterprise_catalog(customer)
        assert catalog.title == 'All Course Runs'
        assert catalog.enterprise_customer == customer

    def test_idempotent(self):
        """Repeated calls do not create duplicate catalogs for the same customer."""
        customer = EnterpriseCustomerFactory(name='Acme Corp')
        get_or_create_enterprise_catalog(customer)
        get_or_create_enterprise_catalog(customer)
        assert EnterpriseCustomerCatalog.objects.filter(enterprise_customer=customer).count() == 1


@patch('enterprise.devstack_api.UserProfile')
@pytest.mark.django_db
class TestGetOrCreateUser(TestCase):
    """Tests for ``get_or_create_user``."""

    def test_creates_user(self, _MockUserProfile):
        """Creates a non-staff user with a generated example.com email."""
        user = get_or_create_user('testuser123')
        assert user.username == 'testuser123'
        assert user.email == 'testuser123@example.com'
        assert user.is_staff is False

    def test_creates_staff_user(self, _MockUserProfile):
        """Honors the ``is_staff`` flag when creating a new user."""
        user = get_or_create_user('staffuser', is_staff=True)
        assert user.is_staff is True

    def test_idempotent_returns_existing(self, _MockUserProfile):
        """Returns the existing user instead of creating a duplicate."""
        get_or_create_user('testuser123')
        user2 = get_or_create_user('testuser123')
        assert user2.username == 'testuser123'
        assert User.objects.filter(username='testuser123').count() == 1


@ddt.ddt
@patch('enterprise.devstack_api.UserProfile')
@pytest.mark.django_db
class TestGetOrCreateEnterpriseUser(TestCase):
    """Tests for ``get_or_create_enterprise_user``."""

    def setUp(self):
        ensure_enterprise_groups()
        self.enterprise = EnterpriseCustomerFactory()
        super().setUp()

    @ddt.data(
        {'username': 'learner_user', 'role': ENTERPRISE_LEARNER_ROLE, 'extra_kwargs': {'enterprise_customer': True}},
        {'username': 'admin_user', 'role': ENTERPRISE_ADMIN_ROLE, 'extra_kwargs': {'enterprise_customer': True}},
        {'username': 'op_user', 'role': ENTERPRISE_OPERATOR_ROLE, 'extra_kwargs': {'applies_to_all_contexts': True}},
    )
    @ddt.unpack
    def test_supported_role(self, _MockUserProfile, username, role, extra_kwargs):
        """Returns a result dict echoing the role for every supported role."""
        kwargs = {'username': username, 'role': role}
        if extra_kwargs.get('enterprise_customer'):
            kwargs['enterprise_customer'] = self.enterprise
        if extra_kwargs.get('applies_to_all_contexts'):
            kwargs['applies_to_all_contexts'] = True
        result = get_or_create_enterprise_user(**kwargs)
        assert result is not None
        assert result['role'] == role

    def test_unknown_role_returns_none(self, _MockUserProfile):
        """Returns None when an unrecognised role string is passed."""
        result = get_or_create_enterprise_user(username='someuser', role='bogus_role')
        assert result is None

    def test_operator_is_staff(self, _MockUserProfile):
        """Operator role provisions the underlying user as staff."""
        result = get_or_create_enterprise_user(
            username='op_user', role=ENTERPRISE_OPERATOR_ROLE, applies_to_all_contexts=True)
        assert result['user'].is_staff is True

    def test_learner_is_not_staff(self, _MockUserProfile):
        """Learner role provisions the underlying user as non-staff."""
        result = get_or_create_enterprise_user(
            username='learner_user', role=ENTERPRISE_LEARNER_ROLE, enterprise_customer=self.enterprise)
        assert result['user'].is_staff is False

    def test_creates_system_wide_role_assignment(self, _MockUserProfile):
        """Creates a SystemWideEnterpriseUserRoleAssignment for the new user."""
        result = get_or_create_enterprise_user(
            username='admin_user',
            role=ENTERPRISE_ADMIN_ROLE,
            enterprise_customer=self.enterprise,
        )
        assert SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user=result['user'],
        ).exists()

    def test_applies_to_all_contexts(self, _MockUserProfile):
        """Propagates ``applies_to_all_contexts=True`` onto the role assignment."""
        result = get_or_create_enterprise_user(
            username='op_user',
            role=ENTERPRISE_OPERATOR_ROLE,
            applies_to_all_contexts=True,
        )
        assignment = SystemWideEnterpriseUserRoleAssignment.objects.get(user=result['user'])
        assert assignment.applies_to_all_contexts is True

    def test_admin_gets_feature_roles(self, _MockUserProfile):
        """Admin role grants all four EnterpriseFeatureUserRoleAssignment rows."""
        result = get_or_create_enterprise_user(
            username='admin_user', role=ENTERPRISE_ADMIN_ROLE, enterprise_customer=self.enterprise)
        assert EnterpriseFeatureUserRoleAssignment.objects.filter(user=result['user']).count() == 4

    def test_learner_gets_no_feature_roles(self, _MockUserProfile):
        """Learner role does not grant any EnterpriseFeatureUserRoleAssignment rows."""
        result = get_or_create_enterprise_user(
            username='learner_user', role=ENTERPRISE_LEARNER_ROLE, enterprise_customer=self.enterprise)
        assert EnterpriseFeatureUserRoleAssignment.objects.filter(user=result['user']).count() == 0


@pytest.mark.django_db
class TestLinkUserToEnterprise(TestCase):
    """Tests for ``link_user_to_enterprise``."""

    def test_creates_link(self):
        """Creates a new active EnterpriseCustomerUser linking the user and customer."""
        user = UserFactory()
        customer = EnterpriseCustomerFactory()
        ecu, created = link_user_to_enterprise(user, customer)
        assert created is True
        assert ecu.user_id == user.pk
        assert ecu.enterprise_customer == customer
        assert ecu.active is True

    def test_inactive_link(self):
        """Honors ``active=False`` when creating the link."""
        user = UserFactory()
        customer = EnterpriseCustomerFactory()
        ecu, _ = link_user_to_enterprise(user, customer, active=False)
        assert ecu.active is False

    def test_idempotent_updates_active(self):
        """Updates the existing link's ``active`` flag instead of creating a duplicate."""
        user = UserFactory()
        customer = EnterpriseCustomerFactory()
        link_user_to_enterprise(user, customer, active=False)
        ecu, created = link_user_to_enterprise(user, customer, active=True)
        assert created is False
        assert ecu.active is True
        assert EnterpriseCustomerUser.objects.filter(user_id=user.pk).count() == 1


@patch('enterprise.devstack_api.CourseEnrollment')
@pytest.mark.django_db
class TestEnrollLearnerInCourse(TestCase):
    """Tests for ``enroll_learner_in_course``."""

    def test_raises_value_error_for_invalid_course_key(self, _MockCourseEnrollment):
        """Raises ValueError when the course key string cannot be parsed."""
        user = UserFactory()
        customer = EnterpriseCustomerFactory()
        with pytest.raises(ValueError, match='Invalid course key'):
            enroll_learner_in_course(user, 'not-a-valid-key', customer)

    def test_raises_does_not_exist_when_not_linked(self, _MockCourseEnrollment):
        """Raises EnterpriseCustomerUser.DoesNotExist when the user is not linked."""
        user = UserFactory()
        customer = EnterpriseCustomerFactory()
        with pytest.raises(EnterpriseCustomerUser.DoesNotExist):
            enroll_learner_in_course(user, 'course-v1:edX+DemoX+Demo_Course', customer)

    def test_creates_enrollments_and_dsc(self, MockCourseEnrollment):
        """Creates EnterpriseCourseEnrollment and granted DSC when ``grant_dsc=True``."""
        user = UserFactory()
        customer = EnterpriseCustomerFactory()
        link_user_to_enterprise(user, customer)

        mock_enrollment = MagicMock()
        mock_enrollment.is_active = True
        MockCourseEnrollment.objects.get_or_create.return_value = (mock_enrollment, True)

        course_id = 'course-v1:edX+DemoX+Demo_Course'
        enroll_learner_in_course(user, course_id, customer, grant_dsc=True)

        assert EnterpriseCourseEnrollment.objects.filter(
            enterprise_customer_user__user_id=user.pk,
            course_id=course_id,
        ).exists()

        dsc = DataSharingConsent.objects.get(
            username=user.username,
            course_id=course_id,
            enterprise_customer=customer,
        )
        assert dsc.granted is True

    def test_activates_inactive_enrollment(self, MockCourseEnrollment):
        """Reactivates an existing inactive CourseEnrollment when re-enrolling."""
        user = UserFactory()
        customer = EnterpriseCustomerFactory()
        link_user_to_enterprise(user, customer)

        mock_enrollment = MagicMock()
        mock_enrollment.is_active = False
        MockCourseEnrollment.objects.get_or_create.return_value = (mock_enrollment, False)

        course_id = 'course-v1:edX+DemoX+Demo_Course'
        enroll_learner_in_course(user, course_id, customer)

        mock_enrollment.activate.assert_called_once()
