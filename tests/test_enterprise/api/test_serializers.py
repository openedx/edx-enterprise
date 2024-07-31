"""
Tests for the `edx-enterprise` serializer module.
"""

import json

import ddt
from oauth2_provider.models import get_application_model
from pytest import mark
from rest_framework.reverse import reverse

from django.conf import settings
from django.contrib.auth.models import Permission
from django.test import TestCase

from enterprise.api.v1.serializers import (
    EnterpriseCustomerApiCredentialSerializer,
    EnterpriseCustomerReportingConfigurationSerializer,
    EnterpriseCustomerSerializer,
    EnterpriseCustomerUserReadOnlySerializer,
    EnterprisePendingCustomerUserSerializer,
    EnterpriseUserSerializer,
    ImmutableStateSerializer,
)
from enterprise.constants import ENTERPRISE_ADMIN_ROLE, ENTERPRISE_LEARNER_ROLE
from enterprise.models import SystemWideEnterpriseRole, SystemWideEnterpriseUserRoleAssignment
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

    def test_group_membership_when_applies_to_all_contexts(self):
        """
        Test that when a group has ``applies_to_all_contexts`` set to True, that group is included in the enterprise
        customer user serializer data when there is an associated via an enterprise customer object.
        """
        enterprise_group = factories.EnterpriseGroupFactory(
            enterprise_customer=self.enterprise_customer_1,
            applies_to_all_contexts=True,
        )
        serializer = EnterpriseCustomerUserReadOnlySerializer(self.enterprise_customer_user_1)
        # Assert the enterprise customer user serializer found the group
        assert serializer.data.get('enterprise_group') == [enterprise_group.uuid]
        # Assert the group has no memberships that could be read by the serializer
        assert not enterprise_group.members.all()

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

        # setup Enteprise Customer
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
        for customer_user, is_admin in [
            # test admin user
            (self.enterprise_customer_user_1, True),
            # test non-admin user
            (self.enterprise_customer_user_2, False),
        ]:
            serializer = EnterpriseUserSerializer(customer_user)
            expected_admin_user = {
                'enterprise_customer_user_id': customer_user.user_id,
                'user_name': customer_user.enterprise_customer.name,
                'user_email': customer_user.enterprise_customer.contact_email,
                'is_admin': is_admin,
                'pending_enterprise_customer_user_id': None,
                'is_pending_admin': False
            }
            serialized_admin_user = serializer.data
            self.assertEqual(expected_admin_user, serialized_admin_user)

    def test_serialize_pending_users(self):
        for pending_customer_user, is_pending_admin in [
            # test pending admin user
            (self.pending_customer_user_one, True),
            # test pending non-admin user
            (self.pending_customer_user_two, False),
        ]:
            serializer = EnterprisePendingCustomerUserSerializer(pending_customer_user)
            expected_pending_admin_user = {
                'enterprise_customer_user_id': None,
                'user_name': None,
                'user_email': pending_customer_user.user_email,
                'is_admin': False,
                'pending_enterprise_customer_user_id': pending_customer_user.id,
                'is_pending_admin': is_pending_admin
            }
            serialized_pending_admin_user = serializer.data
            self.assertEqual(expected_pending_admin_user, serialized_pending_admin_user)
