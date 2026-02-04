"""
Tests for the `edx-enterprise` serializer module.
"""
import datetime
import json
from unittest.mock import Mock, patch

import ddt
import pytz
from oauth2_provider.models import get_application_model
from pytest import mark
from rest_framework.reverse import reverse

from django.conf import settings
from django.contrib.auth.models import Permission
from django.http import HttpRequest
from django.test import TestCase

from enterprise.api.utils import CourseRunProgressStatuses
from enterprise.api.v1.serializers import (
    EnterpriseAdminMemberSerializer,
    EnterpriseAdminMembersRequestQuerySerializer,
    EnterpriseCourseEnrollmentAdminViewSerializer,
    EnterpriseCustomerApiCredentialSerializer,
    EnterpriseCustomerBrandingConfigurationSerializer,
    EnterpriseCustomerReportingConfigurationSerializer,
    EnterpriseCustomerSerializer,
    EnterpriseCustomerUserReadOnlySerializer,
    EnterpriseMembersSerializer,
    EnterpriseSSOUserInfoRequestSerializer,
    EnterpriseUserSerializer,
    ImmutableStateSerializer,
)
from enterprise.constants import ENTERPRISE_ADMIN_ROLE, ENTERPRISE_LEARNER_ROLE
from enterprise.models import (
    EnterpriseCustomerBrandingConfiguration,
    EnterpriseCustomerSupportUsersView,
    SystemWideEnterpriseRole,
    SystemWideEnterpriseUserRoleAssignment,
)
from test_utils import FAKE_UUIDS, TEST_PGP_KEY, TEST_USERNAME, APITest, factories

Application = get_application_model()


@mark.django_db
class TestImmutableStateSerializer(APITest):
    """
    Tests for enterprise API serializers which are immutable.
    """

    def setUp(self):
        """
        Perform operations common for all tests.

        Populate data base for api testing.
        """
        super().setUp()
        self.instance = None
        self.data = {"data": "data"}
        self.validated_data = self.data
        self.serializer = ImmutableStateSerializer(self.data)

    def test_update(self):
        """
        Test ``update`` method of ImmutableStateSerializer.

        Verify that ``update`` for ImmutableStateSerializer returns
        successfully without making any changes.
        """
        with self.assertNumQueries(0):
            self.serializer.update(self.instance, self.validated_data)

    def test_create(self):
        """
        Test ``create`` method of ImmutableStateSerializer.

        Verify that ``create`` for ImmutableStateSerializer returns
        successfully without making any changes.
        """
        with self.assertNumQueries(0):
            self.serializer.create(self.validated_data)


class BaseSerializerTestWithEnterpriseRoleAssignments(TestCase):
    """
    Base test class for serializers that involve enterprise role assignments.
    """

    def setUp(self):
        """
        Perform operations common for all tests.

        """

        super().setUp()
        self.user_1 = factories.UserFactory()
        self.user_2 = factories.UserFactory()
        self.user_3 = factories.UserFactory()
        self.enterprise_customer_user_1 = factories.EnterpriseCustomerUserFactory(user_id=self.user_1.id)
        self.enterprise_customer_user_2 = factories.EnterpriseCustomerUserFactory(user_id=self.user_2.id)
        self.enterprise_customer_user_3 = factories.EnterpriseCustomerUserFactory(user_id=self.user_3.id)
        self.enterprise_customer_1 = self.enterprise_customer_user_1.enterprise_customer
        self.enterprise_customer_2 = self.enterprise_customer_user_2.enterprise_customer

        self.enterprise_admin_role, _ = SystemWideEnterpriseRole.objects.get_or_create(
            name=ENTERPRISE_ADMIN_ROLE,
        )
        self.enterprise_learner_role, _ = SystemWideEnterpriseRole.objects.get_or_create(
            name=ENTERPRISE_LEARNER_ROLE,
        )

        # Clear all current assignments
        SystemWideEnterpriseUserRoleAssignment.objects.all().delete()

        # user 1 has admin and learner role for enterprise 1, admin role for enterprise 2
        factories.SystemWideEnterpriseUserRoleAssignmentFactory(
            role=self.enterprise_admin_role,
            user=self.user_1,
            enterprise_customer=self.enterprise_customer_1
        )
        factories.SystemWideEnterpriseUserRoleAssignmentFactory(
            role=self.enterprise_learner_role,
            user=self.user_1,
            enterprise_customer=self.enterprise_customer_1
        )
        factories.SystemWideEnterpriseUserRoleAssignmentFactory(
            role=self.enterprise_admin_role,
            user=self.user_1,
            enterprise_customer=self.enterprise_customer_2
        )

        # user 2 has learner role for enterprise 2
        factories.SystemWideEnterpriseUserRoleAssignmentFactory(
            role=self.enterprise_learner_role,
            user=self.user_2,
            enterprise_customer=self.enterprise_customer_2
        )

        # user 3 has admin role for enterprise 2
        factories.SystemWideEnterpriseUserRoleAssignmentFactory(
            role=self.enterprise_admin_role,
            user=self.user_3,
            enterprise_customer=self.enterprise_customer_2
        )


@mark.django_db
class TestEnterpriseCustomerSerializer(BaseSerializerTestWithEnterpriseRoleAssignments):
    """
    Tests for EnterpriseCustomerSerializer.
    """

    def test_serialize_admin_users(self):
        serializer = EnterpriseCustomerSerializer(self.enterprise_customer_1)
        expected_admin_users = [{
            'email': self.user_1.email,
            'lms_user_id': self.user_1.id,
        }]
        serialized_admin_users = serializer.data['admin_users']
        self.assertEqual(serialized_admin_users, expected_admin_users)

    def test_serialize_admin_users_many(self):
        serializer = EnterpriseCustomerSerializer([self.enterprise_customer_1, self.enterprise_customer_2], many=True)

        expected_enterprise_customer_1_admin_users = [{
            'email': self.user_1.email,
            'lms_user_id': self.user_1.id,
        }]

        expected_enterprise_customer_2_admin_users = [{
            'email': self.user_1.email,
            'lms_user_id': self.user_1.id,
        }, {
            'email': self.user_3.email,
            'lms_user_id': self.user_3.id,
        }]

        enterprise_customer_1_admin_users = serializer.data[0]['admin_users']
        enterprise_customer_2_admin_users = serializer.data[1]['admin_users']

        self.assertCountEqual(enterprise_customer_1_admin_users, expected_enterprise_customer_1_admin_users)
        self.assertCountEqual(enterprise_customer_2_admin_users, expected_enterprise_customer_2_admin_users)

    def test_serialize_auth_org_id(self):
        serializer = EnterpriseCustomerSerializer(self.enterprise_customer_1)
        expected_auth_org_id = self.enterprise_customer_1.auth_org_id
        serialized_auth_org_id = serializer.data['auth_org_id']
        self.assertEqual(serialized_auth_org_id, expected_auth_org_id)


@mark.django_db
class TestEnterpriseCustomerMembersEndpointLearnersOnly(APITest):
    """
    Tests for the `enterprise-customer-members` API endpoint returns only learners.
    """

    def setUp(self):
        super().setUp()

        self.enterprise_customer = factories.EnterpriseCustomerFactory()
        self.enterprise_uuid = self.enterprise_customer.uuid

        self.learner_user = factories.UserFactory()
        self.admin_user = factories.UserFactory()

        factories.EnterpriseCustomerUserFactory(
            enterprise_customer=self.enterprise_customer,
            user_id=self.learner_user.id,
            linked=True,
            active=True,
        )
        factories.EnterpriseCustomerUserFactory(
            enterprise_customer=self.enterprise_customer,
            user_id=self.admin_user.id,
            linked=True,
            active=True,
        )

        enterprise_admin_role, _ = SystemWideEnterpriseRole.objects.get_or_create(name=ENTERPRISE_ADMIN_ROLE)
        enterprise_learner_role, _ = SystemWideEnterpriseRole.objects.get_or_create(name=ENTERPRISE_LEARNER_ROLE)

        SystemWideEnterpriseUserRoleAssignment.objects.filter(
            enterprise_customer=self.enterprise_customer
        ).delete()

        factories.SystemWideEnterpriseUserRoleAssignmentFactory(
            role=enterprise_learner_role,
            user=self.learner_user,
            enterprise_customer=self.enterprise_customer,
        )
        factories.SystemWideEnterpriseUserRoleAssignmentFactory(
            role=enterprise_admin_role,
            user=self.admin_user,
            enterprise_customer=self.enterprise_customer,
        )

        # Endpoint requires IsAuthenticated
        self.client.force_authenticate(user=self.user)

    def test_returns_only_learners(self):
        url = reverse('enterprise-customer-members', kwargs={'enterprise_uuid': str(self.enterprise_uuid)})
        resp = self.client.get(url)
        assert resp.status_code == 200

        payload = json.loads(resp.content.decode('utf-8'))
        results = payload['results']

        returned_user_ids = {row['enterprise_customer_user']['user_id'] for row in results}

        assert self.learner_user.id in returned_user_ids
        assert self.admin_user.id not in returned_user_ids

    def test_user_id_filter_excludes_non_learner(self):
        url = reverse('enterprise-customer-members', kwargs={'enterprise_uuid': str(self.enterprise_uuid)})
        resp = self.client.get(url, {'user_id': self.admin_user.id})
        assert resp.status_code == 200

        payload = json.loads(resp.content.decode('utf-8'))
        assert payload['results'] == []

    def test_user_query_filter_returns_learner(self):
        url = reverse('enterprise-customer-members', kwargs={'enterprise_uuid': str(self.enterprise_uuid)})
        resp = self.client.get(url, {'user_query': self.learner_user.username})
        assert resp.status_code == 200

        payload = json.loads(resp.content.decode('utf-8'))
        results = payload['results']

        returned_user_ids = {row['enterprise_customer_user']['user_id'] for row in results}
        assert self.learner_user.id in returned_user_ids
        assert self.admin_user.id not in returned_user_ids


@ddt.ddt
@mark.django_db
class TestEnterpriseCustomerUserWriteSerializer(APITest):
    """
    Tests for the ``EnterpriseCustomerUserWriteSerializer``.
    """

    @classmethod
    def setUpClass(cls):
        """
        Perform operations common for all tests once.
        """
        super().setUpClass()
        cls.ent_user_link_url = settings.TEST_SERVER + reverse('enterprise-learner-list')
        cls.permission = Permission.objects.get(name='Can add Enterprise Customer Learner')
        cls.enterprise_uuids = FAKE_UUIDS[:4]
        for enterprise_uuid in cls.enterprise_uuids:
            factories.EnterpriseCustomerFactory(uuid=enterprise_uuid)

    def setUp(self):
        """
        Perform operations common to all tests.
        """
        super().setUp()
        self.user.is_staff = True
        self.user.save()
        self.user.user_permissions.add(self.permission)

    def _link_learner_to_enterprise(self, data, expected_data=None, expected_status_code=201):
        """
        links learner to enterprise and asserts api response has expected status code and data
        """
        response = self.client.post(self.ent_user_link_url, data=data)
        assert response.status_code == expected_status_code
        response = self.load_json(response.content)
        expected_data = expected_data if expected_data else data
        if expected_status_code == 201:
            self.assertDictEqual(expected_data, response)

    @ddt.data(
        (TEST_USERNAME, 201),
        ('non-existing-username', 400),
    )
    @ddt.unpack
    def test_validate_username(self, username, expected_status_code):
        """
        Success for POSTing with users (determined by username) depends on whether the user exists.
        """
        data = {
            'enterprise_customer': self.enterprise_uuids[0],
            'username': username,
        }
        self._link_learner_to_enterprise(data, data.update({'active': True}), expected_status_code)

    def test_active_inactive_enterprise_customers(self):
        """
        Tests activating and de-activating enterprise customer for learner.
        """

        # Link learner with 4 different enterprises
        for enterprise_uuid in self.enterprise_uuids:
            data = {
                'enterprise_customer': enterprise_uuid,
                'username': TEST_USERNAME,
                'active': False,
            }
            self._link_learner_to_enterprise(data)

        # activating one of the existing enterprise should de-activate reset of enterprise
        active_enterprise = self.enterprise_uuids[0]
        expected_inactive_enterprises = list(set(self.enterprise_uuids) - {active_enterprise})
        data['enterprise_customer'] = active_enterprise
        data['active'] = True
        self._link_learner_to_enterprise(data)

        response = self.client.get(self.ent_user_link_url)
        response_json = json.loads(response.content.decode())

        # assert active enterprise is on the top of results
        self.assertEqual(response_json['results'][0]['enterprise_customer']['uuid'], active_enterprise)

        active_enterprises, inactive_enterprises = [], []
        for result in response_json['results']:
            enterprise_uuid = result['enterprise_customer']['uuid']
            if not result['active']:
                inactive_enterprises.append(enterprise_uuid)
            else:
                active_enterprises.append(enterprise_uuid)

        self.assertEqual(len(active_enterprises), 1)
        self.assertEqual(active_enterprises[0], active_enterprise)
        # assert all other enterprises learner is linked to are inactive
        self.assertEqual(sorted(inactive_enterprises), sorted(expected_inactive_enterprises))


@mark.django_db
class TestEnterpriseCustomerUserReadOnlySerializer(BaseSerializerTestWithEnterpriseRoleAssignments):
    """
    Tests for EnterpriseCustomerUserReadOnlySerializer.
    """

    def test_serialize_role_assignments(self):
        """
        Test that role assignments are serialized properly with a single instance.
        """

        serializer = EnterpriseCustomerUserReadOnlySerializer(self.enterprise_customer_user_1)
        assert sorted(serializer.data['role_assignments']) == sorted([ENTERPRISE_LEARNER_ROLE, ENTERPRISE_ADMIN_ROLE])

    def test_serialize_role_assignments_many(self):
        """
        Test that role assignments are serialized properly with many instances.
        """

        serializer = EnterpriseCustomerUserReadOnlySerializer([
            self.enterprise_customer_user_1,
            self.enterprise_customer_user_2,
        ], many=True)

        ecu_1_data = serializer.data[0]
        ecu_2_data = serializer.data[1]
        assert sorted(ecu_1_data['role_assignments']) == sorted([ENTERPRISE_LEARNER_ROLE, ENTERPRISE_ADMIN_ROLE])
        assert ecu_2_data['role_assignments'] == [ENTERPRISE_LEARNER_ROLE]

    def test_group_membership(self):
        """
        Test that group memberships are associated properly with a single instance.
        """

        enterprise_group = factories.EnterpriseGroupFactory(enterprise_customer=self.enterprise_customer_1)
        membership = factories.EnterpriseGroupMembershipFactory(
            enterprise_customer_user=self.enterprise_customer_user_1,
            group=enterprise_group
        )

        serializer = EnterpriseCustomerUserReadOnlySerializer(self.enterprise_customer_user_1)
        assert len(serializer.data['enterprise_group']) == 1
        assert serializer.data['enterprise_group'][0] == membership.group.uuid

    def test_multi_group_membership(self):
        """
        Test that multiple group memberships are associated properly with a single instance.
        """

        enterprise_group = factories.EnterpriseGroupFactory(enterprise_customer=self.enterprise_customer_1)
        enterprise_group_2 = factories.EnterpriseGroupFactory(enterprise_customer=self.enterprise_customer_1)
        membership = factories.EnterpriseGroupMembershipFactory(
            enterprise_customer_user=self.enterprise_customer_user_1,
            group=enterprise_group
        )
        membership_2 = factories.EnterpriseGroupMembershipFactory(
            enterprise_customer_user=self.enterprise_customer_user_1,
            group=enterprise_group_2
        )

        serializer = EnterpriseCustomerUserReadOnlySerializer(self.enterprise_customer_user_1)
        assert len(serializer.data['enterprise_group']) == 2
        assert sorted([membership.group.uuid, membership_2.group.uuid]) == sorted([
            serializer.data['enterprise_group'][0],
            serializer.data['enterprise_group'][1],
        ])


@mark.django_db
class TestEnterpriseCustomerReportingConfigurationSerializer(APITest):
    """
    Tests for EnterpriseCustomerReportingConfigurationSerializer.
    """

    def setUp(self):
        """
        Perform operations common for all tests.

        Populate database for api testing.
        """
        super().setUp()
        self.enterprise_customer = factories.EnterpriseCustomerFactory()
        self.data = {
            "enterprise_customer_id": self.enterprise_customer.uuid,
            "active": True,
            "enable_compression": True,
            "delivery_method": "email",
            "email": ['test@example.com'],
            "frequency": 'daily',
            "day_of_month": 1,
            "day_of_week": 1,
            "hour_of_day": 1,
            "include_date": False,
            "encrypted_password": 'password',
            "encrypted_sftp_password": 'password',
            "data_type": 'progress_v3',
            "report_type": 'json',
            "pgp_encryption_key": '',
        }
        self.validated_data = self.data

    def test_create(self):
        """
        Test ``create`` method of EnterpriseCustomerReportingConfigurationSerializer.
        """
        # Empty PGP key is valid.
        serializer = EnterpriseCustomerReportingConfigurationSerializer(data=self.data)
        assert serializer.is_valid()

        # Use a valid PGP key.
        self.data['pgp_encryption_key'] = TEST_PGP_KEY
        serializer = EnterpriseCustomerReportingConfigurationSerializer(data=self.data)
        assert serializer.is_valid()

        # Invalid PGP key should be flagged.
        self.data['pgp_encryption_key'] = 'invalid-key'
        serializer = EnterpriseCustomerReportingConfigurationSerializer(data=self.data)
        assert not serializer.is_valid()

        # Valid Compression check should be flagged.
        self.data['enable_compression'] = False
        self.data['pgp_encryption_key'] = TEST_PGP_KEY
        serializer = EnterpriseCustomerReportingConfigurationSerializer(data=self.data)
        assert not serializer.is_valid()
        error_message = serializer.errors.get('enable_compression')
        self.assertEqual(
            str(error_message[0]),
            'Compression can only be disabled for the following data types: catalog and delivery method: sftp'
        )


@mark.django_db
class TestEnterpriseCustomerAPICredentialsSerializer(APITest):
    """
    Tests for EnterpriseCustomerAPICredentialsSerializer.
    """

    def setUp(self):
        """
        Perform operations common for all tests.
        Populate database for api testing.
        """
        super().setUp()
        self.user = factories.UserFactory()
        self.data = {
            "name": "New Name",
            "authorization_grant_type": "client-credentials",
            "client_type": "confidential",
            "redirect_uris": "https://example.com/callback",
        }
        self.instance = Application.objects.create(
            name='Old Name',
            authorization_grant_type='client_credentials',
            client_type='confidential',
            redirect_uris='',
            user=self.user
        )
        self.validated_data = self.data

    def test_update(self):
        """
        Test ``update`` method of EnterpriseCustomerAPICredentialsSerializer.
        Verify that ``update`` for EnterpriseCustomerAPICredentialsSerializer returns successfully
        """
        serializer = EnterpriseCustomerApiCredentialSerializer(self.instance, data=self.data)
        assert serializer.is_valid()
        updated_instance = serializer.save()
        self.assertEqual(updated_instance.name, self.data['name'])
        self.assertEqual(updated_instance.authorization_grant_type, self.data['authorization_grant_type'])
        self.assertEqual(updated_instance.client_type, self.data['client_type'])
        self.assertEqual(updated_instance.redirect_uris, self.data['redirect_uris'])


@mark.django_db
class TestEnterpriseUserSerializer(TestCase):
    """
    Tests for EnterpriseCustomerSerializer.
    """
    def setUp(self):
        """
        Perform operations common for all tests.
        """

        super().setUp()

        # setup Enterprise Customer
        self.user_1 = factories.UserFactory()
        self.user_2 = factories.UserFactory()
        self.enterprise_customer_user_1 = factories.EnterpriseCustomerUserFactory(user_id=self.user_1.id)
        self.enterprise_customer_user_2 = factories.EnterpriseCustomerUserFactory(user_id=self.user_2.id)
        self.enterprise_customer_1 = self.enterprise_customer_user_1.enterprise_customer
        self.enterprise_customer_2 = self.enterprise_customer_user_2.enterprise_customer

        self.enterprise_admin_role, _ = SystemWideEnterpriseRole.objects.get_or_create(
            name=ENTERPRISE_ADMIN_ROLE,
        )
        self.enterprise_learner_role, _ = SystemWideEnterpriseRole.objects.get_or_create(
            name=ENTERPRISE_LEARNER_ROLE,
        )

        # Clear all current assignments
        SystemWideEnterpriseUserRoleAssignment.objects.all().delete()

        # user 1 has admin and learner role for enterprise 1
        factories.SystemWideEnterpriseUserRoleAssignmentFactory(
            role=self.enterprise_admin_role,
            user=self.user_1,
            enterprise_customer=self.enterprise_customer_1
        )
        factories.SystemWideEnterpriseUserRoleAssignmentFactory(
            role=self.enterprise_learner_role,
            user=self.user_1,
            enterprise_customer=self.enterprise_customer_1
        )

        # user 2 has learner role for enterprise 2
        factories.SystemWideEnterpriseUserRoleAssignmentFactory(
            role=self.enterprise_learner_role,
            user=self.user_2,
            enterprise_customer=self.enterprise_customer_2
        )

        # setup Pending Enterprise Customer
        self.email_one = 'test_email_1@example.com'
        self.email_two = "test_email_2@example.com"
        self.enterprise_customer_one = factories.EnterpriseCustomerFactory()
        self.enterprise_customer_two = factories.EnterpriseCustomerFactory()
        # admin pending customer user
        self.pending_customer_user_one = factories.PendingEnterpriseCustomerAdminUserFactory(
            enterprise_customer=self.enterprise_customer_one,
            user_email=self.email_one
        )
        # non-admin pending customer user
        self.pending_customer_user_two = factories.PendingEnterpriseCustomerUserFactory(
            enterprise_customer=self.enterprise_customer_two,
            user_email=self.email_two
        )

    def test_serialize_users(self):
        for customer_user, is_admin, role_assignments in [
            # test admin user
            (self.enterprise_customer_user_1, True, [ENTERPRISE_ADMIN_ROLE, ENTERPRISE_LEARNER_ROLE]),
            # test non-admin user
            (self.enterprise_customer_user_2, False, [ENTERPRISE_LEARNER_ROLE]),
        ]:
            user = EnterpriseCustomerSupportUsersView.objects.filter(user_email=customer_user.user.email).first()
            expected_admin_user = {
                'enterprise_customer_user': {
                    'id': user.user_id,
                    'username': user.username,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'email': user.user_email,
                    'is_staff': user.is_staff,
                    'is_active': user.is_active,
                    'date_joined': user.date_joined
                },
                'pending_enterprise_customer_user': None,
                'role_assignments': role_assignments,
                'is_admin': is_admin
            }

            serializer = EnterpriseUserSerializer(user)
            serialized_admin_user = serializer.data

            self.assertEqual(expected_admin_user, serialized_admin_user)

    def test_serialize_pending_users(self):
        for pending_customer_user, is_pending_admin in [
            # test pending admin user
            (self.pending_customer_user_one, True),
            # test pending non-admin user
            (self.pending_customer_user_two, False),
        ]:
            pecu = EnterpriseCustomerSupportUsersView.objects \
                .filter(user_email=pending_customer_user.user_email).first()
            expected_pending_admin_user = {
                'enterprise_customer_user': None,
                'pending_enterprise_customer_user': {
                    'is_pending_admin': is_pending_admin,
                    'is_pending_learner': True,
                    'user_email': pending_customer_user.user_email,
                },
                'role_assignments': None,
                'is_admin': False
            }
            serializer = EnterpriseUserSerializer(pecu)
            serialized_pending_admin_user = serializer.data

            self.assertEqual(expected_pending_admin_user, serialized_pending_admin_user)


class TestEnterpriseMembersSerializer(TestCase):
    """
    Tests for EnterpriseMembersSerializer.
    """

    def setUp(self):
        super().setUp()

        # setup Enterprise Customer
        self.user_1 = factories.UserFactory()
        self.user_2 = factories.UserFactory()
        self.enterprise_customer_user_1 = factories.EnterpriseCustomerUserFactory(user_id=self.user_1.id)
        self.enterprise_customer_user_2 = factories.EnterpriseCustomerUserFactory(user_id=self.user_2.id)
        self.enterprise_customer_1 = self.enterprise_customer_user_1.enterprise_customer
        self.enterprise_customer_2 = self.enterprise_customer_user_2.enterprise_customer

        self.enrollment_1 = factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_customer_user_1,
        )
        self.enrollment_2 = factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_customer_user_1,
        )
        self.enrollment_3 = factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_customer_user_2,
        )

    def test_serialize_users(self):
        expected_user = {
            'enterprise_customer_user': {
                'user_id': self.user_1.id,
                'email': self.user_1.email,
                'joined_org': self.user_1.date_joined.strftime("%b %d, %Y"),
                'name': (self.user_1.first_name + ' ' + self.user_1.last_name),
            },
            'enrollments': 2,
        }

        serializer_input_1 = [
            self.user_1.id,
            self.user_1.email,
            self.user_1.date_joined,
            self.user_1.first_name + ' ' + self.user_1.last_name,
        ]
        serializer = EnterpriseMembersSerializer(serializer_input_1)
        serialized_user = serializer.data

        self.assertEqual(serialized_user, expected_user)

        expected_user_2 = {
            'enterprise_customer_user': {
                'user_id': self.user_2.id,
                'email': self.user_2.email,
                'joined_org': self.user_2.date_joined.strftime("%b %d, %Y"),
                'name': self.user_2.first_name + ' ' + self.user_2.last_name,
            },
            'enrollments': 1,
        }

        serializer_input_2 = [
            self.user_2.id,
            self.user_2.email,
            self.user_2.date_joined,
            self.user_2.first_name + ' ' + self.user_2.last_name,
        ]

        serializer = EnterpriseMembersSerializer(serializer_input_2)
        serialized_user = serializer.data
        self.assertEqual(serialized_user, expected_user_2)


class TestEnterpriseCustomerBrandingConfigurationSerializer(TestCase):
    """
    Tests for EnterpriseCustomerBrandingConfigurationSerializer.
    """

    def setUp(self):
        super().setUp()
        self.enterprise_customer = factories.EnterpriseCustomerFactory()

    def test_branding_configuration(self):
        branding_config = EnterpriseCustomerBrandingConfiguration(
            enterprise_customer=self.enterprise_customer)

        branding_config.logo = 'https://example.com/logo.png'
        branding_config.primary_color = '#000000'
        branding_config.secondary_color = '#FFFFFF'
        branding_config.tertiary_color = '#0000FF'
        branding_config.save()

        saved_config = EnterpriseCustomerBrandingConfiguration.objects.get(
            enterprise_customer=self.enterprise_customer)

        serializer = EnterpriseCustomerBrandingConfigurationSerializer(saved_config)
        data = serializer.data
        self.assertEqual(data['primary_color'], branding_config.primary_color)
        self.assertEqual(data['secondary_color'], branding_config.secondary_color)
        self.assertEqual(data['tertiary_color'], branding_config.tertiary_color)
        self.assertEqual(data['logo'], branding_config.logo)


@mark.django_db
class TestEnterpriseCourseEnrollmentAdminViewSerializer(TestCase):
    """ Unit tests for EnterpriseCourseEnrollmentAdminViewSerializer. """

    def setUp(self):
        """ Set up test data. """
        super().setUp()
        self.user = factories.UserFactory.create(is_staff=True, is_active=True)
        self.enterprise_customer_user = factories.EnterpriseCustomerUserFactory(
            user_id=self.user.id,
        )
        self.enterprise_customer = self.enterprise_customer_user.enterprise_customer

    @patch.object(HttpRequest, 'get_host', return_value='example.edx.org')
    @patch('enterprise.api.v1.serializers.CourseDetails')
    @patch('enterprise.models.CourseEnrollment')
    @patch('enterprise.api.v1.serializers.get_certificate_for_user')
    def test_enterprise_course_enrollment_serialization_with_course_details(
        self,
        mock_get_certificate,
        mock_course_enrollment_class,
        mock_course_details_class,
        _,
    ):
        """
        EnterpriseCourseEnrollmentAdminViewSerializer should create proper representation
        with course details based on the instance data it receives (an enterprise course enrollment)
        """
        course_run_id = 'course-v1:edX+DemoX+2024'
        enrollment = factories.EnterpriseCourseEnrollmentFactory.create(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=course_run_id,
        )

        course_overviews = [{
            'id': course_run_id,
            'start': '2024-01-01T00:00:00Z',
            'end': '2024-06-01T00:00:00Z',
            'display_name_with_default': 'Demo Course',
            'display_org_with_default': 'edX',
            'pacing': 'self-paced',
            'has_ended': True,
        }]

        mock_course_details = Mock(
            id=course_run_id,
            course_key='DemoX',
            course_type='verified',
            product_source='edx',
            start_date='2023-01-01T00:00:00Z',
            end_date='2025-01-01T00:00:00Z',
            enroll_by='2024-10-01T00:00:00Z',
        )

        mock_get_certificate.return_value = {
            'download_url': 'example.com',
            'is_passing': True,
            'created': '2024-01-01T00:00:00Z',
        }
        request = HttpRequest()
        serializer_context = {
            'request': request,
            'enterprise_customer_user': self.enterprise_customer_user,
            'course_overviews': course_overviews
        }
        mock_course_enrollment_class.objects.get.return_value.is_active = True
        mock_course_enrollment_class.objects.get.return_value.mode = 'verified'
        mock_course_enrollment_class.objects.get.return_value.created = '2024-01-01T00:00:00Z'
        mock_course_details_class.objects.filter.return_value.first.return_value = mock_course_details
        serializer = EnterpriseCourseEnrollmentAdminViewSerializer(
            [enrollment],
            many=True,
            context=serializer_context
        )
        serialized_data = serializer.data[0]

        assert serialized_data['course_run_id'] == course_run_id
        assert serialized_data['created'] == enrollment.created.isoformat()
        assert serialized_data['start_date'] == mock_course_details.start_date
        assert serialized_data['end_date'] == mock_course_details.end_date
        assert serialized_data['display_name'] == 'Demo Course'
        assert serialized_data['org_name'] == 'edX'
        assert serialized_data['pacing'] == 'self-paced'
        assert serialized_data['is_revoked'] is False
        assert serialized_data['is_enrollment_active'] is True
        assert serialized_data['mode'] == 'verified'
        assert serialized_data['course_key'] == 'DemoX'
        assert serialized_data['course_type'] == 'verified'
        assert serialized_data['product_source'] == 'edx'
        assert serialized_data['enroll_by'] == '2024-10-01T00:00:00Z'

    @patch.object(HttpRequest, 'get_host', return_value='example.edx.org')
    @patch('enterprise.models.CourseEnrollment')
    @patch('enterprise.api.v1.serializers.get_certificate_for_user')
    def test_enterprise_course_enrollment_serialization_without_course_details(
        self,
        mock_get_certificate,
        mock_course_enrollment_class,
        _,
    ):
        """
        EnterpriseCourseEnrollmentAdminViewSerializer should create proper representation
        without course details based on the instance data it receives (an enterprise course enrollment)
        """
        course_run_id = 'course-v1:edX+DemoX+2024'
        enrollment = factories.EnterpriseCourseEnrollmentFactory.create(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=course_run_id,
        )

        course_overviews = [{
            'id': course_run_id,
            'start': '2024-01-01T00:00:00Z',
            'end': '2024-06-01T00:00:00Z',
            'display_name_with_default': 'Demo Course',
            'display_org_with_default': 'edX',
            'pacing': 'self-paced',
            'has_ended': True,
        }]

        mock_get_certificate.return_value = {
            'download_url': 'example.com',
            'is_passing': True,
            'created': '2024-01-01T00:00:00Z',
        }
        request = HttpRequest()
        serializer_context = {
            'request': request,
            'enterprise_customer_user': self.enterprise_customer_user,
            'course_overviews': course_overviews
        }
        mock_course_enrollment_class.objects.get.return_value.is_active = True
        mock_course_enrollment_class.objects.get.return_value.mode = 'verified'
        mock_course_enrollment_class.objects.get.return_value.created = '2024-01-01T00:00:00Z'
        serializer = EnterpriseCourseEnrollmentAdminViewSerializer(
            [enrollment],
            many=True,
            context=serializer_context
        )
        serialized_data = serializer.data[0]

        assert serialized_data['course_run_id'] == course_run_id
        assert serialized_data['created'] == enrollment.created.isoformat()
        assert serialized_data['start_date'] == '2024-01-01T00:00:00Z'
        assert serialized_data['end_date'] == '2024-06-01T00:00:00Z'
        assert serialized_data['display_name'] == 'Demo Course'
        assert serialized_data['org_name'] == 'edX'
        assert serialized_data['pacing'] == 'self-paced'
        assert serialized_data['is_revoked'] is False
        assert serialized_data['is_enrollment_active'] is True
        assert serialized_data['mode'] == 'verified'
        self.assertIsNone(serialized_data.get('course_key'))
        self.assertIsNone(serialized_data.get('course_type'))
        self.assertIsNone(serialized_data.get('product_source'))
        self.assertIsNone(serialized_data.get('enroll_by'))

    @patch.object(HttpRequest, 'get_host', return_value='example.edx.org')
    @patch('enterprise.api.v1.serializers.datetime')
    @patch('enterprise.api.v1.serializers.CourseDetails')
    @patch('enterprise.models.CourseEnrollment')
    @patch('enterprise.api.v1.serializers.get_certificate_for_user')
    def test_enterprise_course_enrollment_serialization_with_exec_ed(
        self,
        mock_get_certificate,
        mock_course_enrollment_class,
        mock_course_details_class,
        mock_datetime,
        _,
    ):
        """
        EnterpriseCourseEnrollmentAdminViewSerializer should create proper representation
        with course details and exec ed based on the instance data it receives
        (an enterprise course enrollment)
        """
        course_run_id = 'course-v1:edX+DemoX+2024'
        enrollment = factories.EnterpriseCourseEnrollmentFactory.create(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=course_run_id,
        )

        course_overviews = [{
            'id': course_run_id,
            'start': '2024-01-01T00:00:00Z',
            'end': '2024-06-01T00:00:00Z',
            'display_name_with_default': 'Demo Course',
            'display_org_with_default': 'edX',
            'pacing': 'self-paced',
            'has_ended': True,
        }]

        mock_course_details = Mock(
            id=course_run_id,
            course_key='DemoX',
            course_type='executive-education-2u',
            product_source='2u',
            start_date=datetime.datetime(2023, 1, 1, tzinfo=pytz.UTC),
            end_date=datetime.datetime(2025, 1, 1, tzinfo=pytz.UTC),
            enroll_by=datetime.datetime(2024, 10, 1, tzinfo=pytz.UTC),
        )

        mock_get_certificate.return_value = {
            'download_url': 'example.com',
            'is_passing': True,
            'created': '2024-01-01T00:00:00Z',
        }
        mock_datetime.datetime.now.return_value = datetime.datetime(2023, 1, 1, tzinfo=pytz.UTC)
        request = HttpRequest()
        serializer_context = {
            'request': request,
            'enterprise_customer_user': self.enterprise_customer_user,
            'course_overviews': course_overviews
        }
        mock_course_enrollment_class.objects.get.return_value.is_active = True
        mock_course_enrollment_class.objects.get.return_value.mode = 'verified'
        mock_course_enrollment_class.objects.get.return_value.created = '2024-01-01T00:00:00Z'
        mock_course_details_class.objects.filter.return_value.first.return_value = mock_course_details
        serializer = EnterpriseCourseEnrollmentAdminViewSerializer(
            [enrollment],
            many=True,
            context=serializer_context
        )
        serialized_data = serializer.data[0]

        assert serialized_data['course_run_id'] == course_run_id
        assert serialized_data['created'] == enrollment.created.isoformat()
        assert serialized_data['start_date'] == mock_course_details.start_date
        assert serialized_data['end_date'] == mock_course_details.end_date
        assert serialized_data['display_name'] == 'Demo Course'
        assert serialized_data['org_name'] == 'edX'
        assert serialized_data['pacing'] == 'self-paced'
        assert serialized_data['is_revoked'] is False
        assert serialized_data['is_enrollment_active'] is True
        assert serialized_data['mode'] == 'verified'
        assert serialized_data['course_key'] == 'DemoX'
        assert serialized_data['course_type'] == 'executive-education-2u'
        assert serialized_data['product_source'] == '2u'
        assert serialized_data['enroll_by'] == mock_course_details.enroll_by
        assert serialized_data['course_run_status'] == 'completed'


@mark.django_db
class TestGetExecEdCourseRunStatus(TestCase):
    """Unit tests for _get_exec_ed_course_run_status function."""

    def setUp(self):
        """Set up test data."""
        super().setUp()
        self.serializer = EnterpriseCourseEnrollmentAdminViewSerializer()
        self.now = datetime.datetime.now(pytz.utc)
        self.course_details = Mock(
            start_date=self.now,
            end_date=self.now + datetime.timedelta(days=30)
        )
        self.enterprise_enrollment = Mock(saved_for_later=False)

    @patch('enterprise.api.v1.serializers.datetime')
    def test_saved_for_later(self, mock_datetime):
        """Test that a course marked as saved for later returns SAVED_FOR_LATER status."""
        mock_datetime.datetime.now.return_value = self.now
        self.enterprise_enrollment.saved_for_later = True
        # pylint: disable=protected-access
        status = self.serializer._get_exec_ed_course_run_status(
            self.course_details,
            {'is_passing': False},
            self.enterprise_enrollment
        )
        assert status == CourseRunProgressStatuses.SAVED_FOR_LATER

    @patch('enterprise.api.v1.serializers.datetime')
    def test_completed_with_certificate(self, mock_datetime):
        """Test that a course with a passing certificate returns COMPLETED status."""
        mock_datetime.datetime.now.return_value = self.now
        # pylint: disable=protected-access
        status = self.serializer._get_exec_ed_course_run_status(
            self.course_details,
            {'is_passing': True},
            self.enterprise_enrollment
        )
        assert status == CourseRunProgressStatuses.COMPLETED

    @patch('enterprise.api.v1.serializers.datetime')
    def test_completed_with_ended_course(self, mock_datetime):
        """Test that a course that has ended returns COMPLETED status."""
        mock_datetime.datetime.now.return_value = self.course_details.end_date + datetime.timedelta(days=1)
        # pylint: disable=protected-access
        status = self.serializer._get_exec_ed_course_run_status(
            self.course_details,
            {'is_passing': False},
            self.enterprise_enrollment
        )
        assert status == CourseRunProgressStatuses.COMPLETED

    @patch('enterprise.api.v1.serializers.datetime')
    def test_in_progress(self, mock_datetime):
        """Test that a course that has started but not ended returns IN_PROGRESS status."""
        mock_datetime.datetime.now.return_value = self.course_details.start_date + datetime.timedelta(days=1)
        # pylint: disable=protected-access
        status = self.serializer._get_exec_ed_course_run_status(
            self.course_details,
            {'is_passing': False},
            self.enterprise_enrollment
        )
        assert status == CourseRunProgressStatuses.IN_PROGRESS

    @patch('enterprise.api.v1.serializers.datetime')
    def test_upcoming(self, mock_datetime):
        """Test that a course that hasn't started yet returns UPCOMING status."""
        mock_datetime.datetime.now.return_value = self.course_details.start_date - datetime.timedelta(days=1)
        # pylint: disable=protected-access
        status = self.serializer._get_exec_ed_course_run_status(
            self.course_details,
            {'is_passing': False},
            self.enterprise_enrollment
        )
        assert status == CourseRunProgressStatuses.UPCOMING


@ddt.ddt
@mark.django_db
class TestEnterpriseSSOUserInfoRequestSerializer(TestCase):
    """
    Tests for EnterpriseSSOUserInfoRequestSerializer.
    """

    def test_valid_serializer(self):
        """
        Test serializer with valid data.
        """
        data = {
            'org_id': 'test-org-123',
            'external_user_id': 'user-456'
        }
        serializer = EnterpriseSSOUserInfoRequestSerializer(data=data)

        assert serializer.is_valid()
        assert serializer.validated_data['org_id'] == 'test-org-123'
        assert serializer.validated_data['external_user_id'] == 'user-456'

    def test_missing_org_id(self):
        """
        Test serializer with missing org_id field.
        """
        data = {
            'external_user_id': 'user-456'
        }
        serializer = EnterpriseSSOUserInfoRequestSerializer(data=data)

        assert not serializer.is_valid()
        assert 'org_id' in serializer.errors
        assert serializer.errors['org_id'][0].code == 'required'

    def test_missing_external_user_id(self):
        """
        Test serializer with missing external_user_id field.
        """
        data = {
            'org_id': 'test-org-123'
        }
        serializer = EnterpriseSSOUserInfoRequestSerializer(data=data)

        assert not serializer.is_valid()
        assert 'external_user_id' in serializer.errors
        assert serializer.errors['external_user_id'][0].code == 'required'

    def test_missing_both_fields(self):
        """
        Test serializer with missing both required fields.
        """
        data = {}
        serializer = EnterpriseSSOUserInfoRequestSerializer(data=data)

        assert not serializer.is_valid()
        assert 'org_id' in serializer.errors
        assert 'external_user_id' in serializer.errors
        assert serializer.errors['org_id'][0].code == 'required'
        assert serializer.errors['external_user_id'][0].code == 'required'

    @ddt.data(
        {'org_id': '', 'external_user_id': 'user-456'},
        {'org_id': 'test-org-123', 'external_user_id': ''},
        {'org_id': '', 'external_user_id': ''},
    )
    def test_empty_field_values(self, data):
        """
        Test serializer with empty field values.
        """
        serializer = EnterpriseSSOUserInfoRequestSerializer(data=data)

        assert not serializer.is_valid()
        for field_name, field_value in data.items():
            if field_value == '':
                assert field_name in serializer.errors
                assert serializer.errors[field_name][0].code == 'blank'

    def test_extra_fields_ignored(self):
        """
        Test serializer ignores extra fields not defined in schema.
        """
        data = {
            'org_id': 'test-org-123',
            'external_user_id': 'user-456',
            'extra_field': 'should_be_ignored'
        }
        serializer = EnterpriseSSOUserInfoRequestSerializer(data=data)

        assert serializer.is_valid()
        assert serializer.validated_data['org_id'] == 'test-org-123'
        assert serializer.validated_data['external_user_id'] == 'user-456'
        assert 'extra_field' not in serializer.validated_data


@mark.django_db
class TestEnterpriseAdminMemberSerializer(TestCase):
    """
    Tests for EnterpriseAdminMemberSerializer.
    """

    def test_serializer_with_admin_user_is_valid(self):
        data = {
            "id": 10,
            "name": "admin_user",
            "email": "admin@test.com",
            "joined_date": "2024-01-01T10:00:00Z",
            "invited_date": None,
            "status": "Admin",
        }

        serializer = EnterpriseAdminMemberSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["status"] == "Admin"
        assert serializer.validated_data["email"] == "admin@test.com"
        assert serializer.validated_data["name"] == "admin_user"

    def test_serializer_with_pending_user_is_valid(self):
        data = {
            "id": 1,
            "name": None,
            "email": "pending@test.com",
            "invited_date": "2024-01-02T12:00:00Z",
            "joined_date": None,
            "status": "Pending",
        }

        serializer = EnterpriseAdminMemberSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["status"] == "Pending"
        assert serializer.validated_data["email"] == "pending@test.com"
        assert serializer.validated_data["name"] is None
        assert serializer.validated_data["joined_date"] is None

    def test_serializer_missing_email_fails(self):
        serializer = EnterpriseAdminMemberSerializer(data={"id": 1, "status": "Admin"})
        assert not serializer.is_valid()
        assert "email" in serializer.errors


@mark.django_db
class TestEnterpriseAdminMembersRequestQuerySerializer(TestCase):
    """
    Tests for EnterpriseAdminMembersRequestQuerySerializer.
    """

    def test_defaults(self):
        serializer = EnterpriseAdminMembersRequestQuerySerializer(data={})
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["sort_by"] == "name"
        assert serializer.validated_data["is_reversed"] is False
        # user_query is optional, so it may not be present in validated_data

    def test_valid_query_params(self):
        serializer = EnterpriseAdminMembersRequestQuerySerializer(
            data={
                "user_query": "admin",
                "sort_by": "email",
                "is_reversed": True,
            }
        )
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["user_query"] == "admin"
        assert serializer.validated_data["sort_by"] == "email"
        assert serializer.validated_data["is_reversed"] is True

    def test_user_query_allows_blank_and_trims(self):
        serializer = EnterpriseAdminMembersRequestQuerySerializer(
            data={"user_query": "   "}
        )
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["user_query"] == ""

    def test_invalid_sort_by_fails(self):
        serializer = EnterpriseAdminMembersRequestQuerySerializer(
            data={"sort_by": "drop table users;"}
        )
        assert not serializer.is_valid()
        assert "sort_by" in serializer.errors

    def test_invalid_is_reversed_fails(self):
        serializer = EnterpriseAdminMembersRequestQuerySerializer(
            data={"is_reversed": "not-a-boolean"}
        )
        assert not serializer.is_valid()
        assert "is_reversed" in serializer.errors
