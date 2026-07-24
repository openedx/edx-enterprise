"""
Tests for the devstack-only helpers in ``enterprise/devstack_api.py``.
"""

import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch

import ddt
import pytest

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.sites.models import Site
from django.test import TestCase, override_settings

from consent.models import DataSharingConsent
from enterprise.constants import (
    ENTERPRISE_ADMIN_ROLE,
    ENTERPRISE_DATA_API_ACCESS_GROUP,
    ENTERPRISE_ENROLLMENT_API_ACCESS_GROUP,
    ENTERPRISE_LEARNER_ROLE,
    ENTERPRISE_OPERATOR_ROLE,
)
from enterprise.devstack_api import (
    delete_user_and_enterprise_links,
    enroll_learner_in_course,
    ensure_enterprise_groups,
    get_or_create_enterprise_branding,
    get_or_create_enterprise_catalog,
    get_or_create_enterprise_customer,
    get_or_create_enterprise_identity_provider,
    get_or_create_enterprise_user,
    get_or_create_site,
    get_or_create_user,
    link_user_to_enterprise,
    seed_global_users,
)
from enterprise.models import (
    EnterpriseCourseEnrollment,
    EnterpriseCustomer,
    EnterpriseCustomerBrandingConfiguration,
    EnterpriseCustomerCatalog,
    EnterpriseCustomerIdentityProvider,
    EnterpriseCustomerUser,
    EnterpriseFeatureUserRoleAssignment,
    PendingEnterpriseCustomerUser,
    SystemWideEnterpriseUserRoleAssignment,
)
from test_utils.factories import EnterpriseCustomerFactory, PendingEnterpriseCustomerUserFactory, UserFactory

User = get_user_model()

# A minimal valid 1x1 PNG, used to exercise the logo-upload path.
_MINIMAL_PNG = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
    b'\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01'
    b'\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
)


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

    def test_uses_explicit_email(self, _MockUserProfile):
        """Uses the supplied email instead of the generated default."""
        user = get_or_create_user('testuser123', email='custom@corp.example')
        assert user.email == 'custom@corp.example'

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

    def test_sets_first_and_last_name(self, _MockUserProfile):
        """Sets the given/surname on the User when supplied."""
        user = get_or_create_user('godric1', first_name='Godric', last_name='Gryffindor')
        assert user.first_name == 'Godric'
        assert user.last_name == 'Gryffindor'

    def test_profile_name_from_first_last(self, MockUserProfile):
        """Derives the profile name from the supplied first/last name."""
        get_or_create_user('godric1', first_name='Godric', last_name='Gryffindor')
        _, kwargs = MockUserProfile.objects.update_or_create.call_args
        assert kwargs['defaults']['name'] == 'Godric Gryffindor'

    def test_profile_name_defaults_without_names(self, MockUserProfile):
        """Falls back to a generic profile name when no first/last is given."""
        get_or_create_user('nameless1')
        _, kwargs = MockUserProfile.objects.update_or_create.call_args
        assert kwargs['defaults']['name'] == 'Test Enterprise User'


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
        """Returns the created user for every supported role."""
        kwargs = {'username': username, 'role': role}
        if extra_kwargs.get('enterprise_customer'):
            kwargs['enterprise_customer'] = self.enterprise
        if extra_kwargs.get('applies_to_all_contexts'):
            kwargs['applies_to_all_contexts'] = True
        result = get_or_create_enterprise_user(**kwargs)
        assert result is not None
        assert result.username == username

    def test_unknown_role_returns_none(self, _MockUserProfile):
        """Returns None when an unrecognised role string is passed."""
        result = get_or_create_enterprise_user(username='someuser', role='bogus_role')
        assert result is None

    def test_operator_is_staff(self, _MockUserProfile):
        """Operator role provisions the underlying user as staff."""
        result = get_or_create_enterprise_user(
            username='op_user', role=ENTERPRISE_OPERATOR_ROLE, applies_to_all_contexts=True)
        assert result.is_staff is True

    def test_learner_is_not_staff(self, _MockUserProfile):
        """Learner role provisions the underlying user as non-staff."""
        result = get_or_create_enterprise_user(
            username='learner_user', role=ENTERPRISE_LEARNER_ROLE, enterprise_customer=self.enterprise)
        assert result.is_staff is False

    def test_creates_system_wide_role_assignment(self, _MockUserProfile):
        """Creates a SystemWideEnterpriseUserRoleAssignment for the new user."""
        result = get_or_create_enterprise_user(
            username='admin_user',
            role=ENTERPRISE_ADMIN_ROLE,
            enterprise_customer=self.enterprise,
        )
        assert SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user=result,
        ).exists()

    def test_applies_to_all_contexts(self, _MockUserProfile):
        """Propagates ``applies_to_all_contexts=True`` onto the role assignment."""
        result = get_or_create_enterprise_user(
            username='op_user',
            role=ENTERPRISE_OPERATOR_ROLE,
            applies_to_all_contexts=True,
        )
        assignment = SystemWideEnterpriseUserRoleAssignment.objects.get(user=result)
        assert assignment.applies_to_all_contexts is True

    def test_admin_gets_feature_roles(self, _MockUserProfile):
        """Admin role grants all four EnterpriseFeatureUserRoleAssignment rows."""
        result = get_or_create_enterprise_user(
            username='admin_user', role=ENTERPRISE_ADMIN_ROLE, enterprise_customer=self.enterprise)
        assert EnterpriseFeatureUserRoleAssignment.objects.filter(user=result).count() == 4

    def test_learner_gets_no_feature_roles(self, _MockUserProfile):
        """Learner role does not grant any EnterpriseFeatureUserRoleAssignment rows."""
        result = get_or_create_enterprise_user(
            username='learner_user', role=ENTERPRISE_LEARNER_ROLE, enterprise_customer=self.enterprise)
        assert EnterpriseFeatureUserRoleAssignment.objects.filter(user=result).count() == 0

    def test_email_and_name_passthrough(self, _MockUserProfile):
        """email/first_name/last_name are passed through to the created User."""
        result = get_or_create_enterprise_user(
            username='godric_learner',
            role=ENTERPRISE_LEARNER_ROLE,
            enterprise_customer=self.enterprise,
            email='godric@corp.example',
            first_name='Godric',
            last_name='Gryffindor',
        )
        assert result.email == 'godric@corp.example'
        assert result.first_name == 'Godric'
        assert result.last_name == 'Gryffindor'


@patch('enterprise.devstack_api.UserProfile')
@pytest.mark.django_db
class TestSeedGlobalUsers(TestCase):
    """Tests for ``seed_global_users``."""

    EXPECTED_USERNAMES = {
        'enterprise_admin',
        'enterprise_openedx_operator',
        'license-manager_worker',
        'enterprise-catalog_worker',
        'enterprise_worker',
        'ecommerce_worker',
    }

    def setUp(self):
        ensure_enterprise_groups()
        super().setUp()

    def test_creates_expected_users(self, _MockUserProfile):
        """Creates exactly the six shared global users and returns them as User objects."""
        result = seed_global_users()
        assert {user.username for user in result} == self.EXPECTED_USERNAMES
        assert User.objects.filter(username__in=self.EXPECTED_USERNAMES).count() == 6

    def test_roles_apply_to_all_contexts(self, _MockUserProfile):
        """Every global user's role assignment spans all enterprise contexts."""
        seed_global_users()
        assignments = SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user__username__in=self.EXPECTED_USERNAMES,
        )
        assert assignments.count() == 6
        assert all(assignment.applies_to_all_contexts for assignment in assignments)
        assert all(assignment.enterprise_customer is None for assignment in assignments)

    def test_not_linked_to_any_enterprise(self, _MockUserProfile):
        """Global users are never linked to a specific enterprise (Option C)."""
        seed_global_users()
        global_user_ids = User.objects.filter(
            username__in=self.EXPECTED_USERNAMES,
        ).values_list('id', flat=True)
        assert not EnterpriseCustomerUser.objects.filter(user_id__in=global_user_ids).exists()

    def test_idempotent(self, _MockUserProfile):
        """Calling twice creates no duplicate users or role assignments."""
        seed_global_users()
        seed_global_users()
        assert User.objects.filter(username__in=self.EXPECTED_USERNAMES).count() == 6
        assert SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user__username__in=self.EXPECTED_USERNAMES,
        ).count() == 6


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


@pytest.mark.django_db
class TestGetOrCreateEnterpriseBranding(TestCase):
    """Tests for ``get_or_create_enterprise_branding``."""

    def setUp(self):
        self.customer = EnterpriseCustomerFactory()
        super().setUp()

    def _write_png(self, name):
        """Write a minimal PNG to a fresh temp dir and return its path."""
        tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp_dir, ignore_errors=True)
        path = os.path.join(tmp_dir, name)
        with open(path, 'wb') as png_file:
            png_file.write(_MINIMAL_PNG)
        return path

    def _temp_media_root(self):
        """Return a throwaway MEDIA_ROOT that is cleaned up after the test."""
        media_root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media_root, ignore_errors=True)
        return media_root

    def test_creates_branding_with_colors(self):
        """Creates a branding config and applies every supplied accent color."""
        branding = get_or_create_enterprise_branding(
            self.customer,
            primary_color='#740001',
            secondary_color='#D3A625',
            tertiary_color='#EEBA30',
        )
        assert branding.enterprise_customer == self.customer
        assert branding.primary_color == '#740001'
        assert branding.secondary_color == '#D3A625'
        assert branding.tertiary_color == '#EEBA30'
        assert not branding.logo

    def test_idempotent(self):
        """Repeated calls update the single branding row instead of duplicating it."""
        get_or_create_enterprise_branding(self.customer, primary_color='#740001')
        branding = get_or_create_enterprise_branding(self.customer, primary_color='#1A472A')
        assert branding.primary_color == '#1A472A'
        assert EnterpriseCustomerBrandingConfiguration.objects.filter(
            enterprise_customer=self.customer,
        ).count() == 1

    def test_missing_logo_path_leaves_logo_unset(self):
        """A logo_path with no file on disk is skipped, but colors are still applied."""
        branding = get_or_create_enterprise_branding(
            self.customer,
            logo_path='/nonexistent/does-not-exist.png',
            primary_color='#740001',
        )
        assert not branding.logo
        assert branding.primary_color == '#740001'

    def test_sets_logo_from_path(self):
        """A valid logo_path uploads the image and records it on the config."""
        logo_path = self._write_png('gryffindor.png')
        with override_settings(MEDIA_ROOT=self._temp_media_root()):
            branding = get_or_create_enterprise_branding(self.customer, logo_path=logo_path)
        assert branding.logo
        assert branding.logo.name.endswith('.png')

    def test_existing_logo_not_overwritten(self):
        """A second call does not replace a logo the config already has."""
        first_path = self._write_png('first.png')
        second_path = self._write_png('second.png')
        with override_settings(MEDIA_ROOT=self._temp_media_root()):
            first = get_or_create_enterprise_branding(self.customer, logo_path=first_path)
            first_name = first.logo.name
            second = get_or_create_enterprise_branding(self.customer, logo_path=second_path)
        assert second.logo.name == first_name


@pytest.mark.django_db
class TestGetOrCreateEnterpriseIdentityProvider(TestCase):
    """Tests for ``get_or_create_enterprise_identity_provider``."""

    def test_creates_link(self):
        """Creates the IdP link for the given customer and provider_id."""
        customer = EnterpriseCustomerFactory()
        ecidp = get_or_create_enterprise_identity_provider(customer, 'saml-gryffindor')
        assert ecidp.enterprise_customer == customer
        assert ecidp.provider_id == 'saml-gryffindor'

    def test_idempotent(self):
        """Repeated calls do not create a duplicate link for the same provider_id."""
        customer = EnterpriseCustomerFactory()
        get_or_create_enterprise_identity_provider(customer, 'saml-gryffindor')
        get_or_create_enterprise_identity_provider(customer, 'saml-gryffindor')
        assert EnterpriseCustomerIdentityProvider.objects.filter(
            provider_id='saml-gryffindor',
        ).count() == 1


@pytest.mark.django_db
class TestDeleteUserAndEnterpriseLinks(TestCase):
    """Tests for ``delete_user_and_enterprise_links``."""

    def test_deletes_user_and_returns_count(self):
        """Deletes a matching user and reports one deletion."""
        UserFactory(email='newcomer@example.com')
        deleted = delete_user_and_enterprise_links('newcomer@example.com')
        assert deleted == 1
        assert not User.objects.filter(email='newcomer@example.com').exists()

    def test_deletes_enterprise_customer_user(self):
        """Removes the non-cascading EnterpriseCustomerUser rows for the user."""
        customer = EnterpriseCustomerFactory()
        user = UserFactory(email='newcomer@example.com')
        link_user_to_enterprise(user, customer)
        delete_user_and_enterprise_links('newcomer@example.com')
        assert not EnterpriseCustomerUser.objects.filter(user_id=user.pk).exists()

    def test_deletes_pending_enterprise_customer_user(self):
        """Clears the email-keyed PendingEnterpriseCustomerUser too."""
        PendingEnterpriseCustomerUserFactory(user_email='newcomer@example.com')
        delete_user_and_enterprise_links('newcomer@example.com')
        assert not PendingEnterpriseCustomerUser.objects.filter(
            user_email='newcomer@example.com',
        ).exists()

    def test_no_match_returns_zero(self):
        """Returns 0 and does not error when no user has the given email."""
        deleted = delete_user_and_enterprise_links('absent@example.com')
        assert deleted == 0

    def test_leaves_other_users_untouched(self):
        """Only deletes users whose email matches."""
        keep = UserFactory(email='keep@example.com')
        UserFactory(email='remove@example.com')
        delete_user_and_enterprise_links('remove@example.com')
        assert User.objects.filter(pk=keep.pk).exists()
