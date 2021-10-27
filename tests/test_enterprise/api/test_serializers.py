"""
Tests for the `edx-enterprise` serializer module.
"""

import json

import ddt
from pytest import mark
from rest_framework.reverse import reverse

from django.conf import settings
from django.contrib.auth.models import Permission
from django.test import TestCase

from enterprise.api.v1.serializers import EnterpriseCustomerUserReadOnlySerializer, ImmutableStateSerializer
from enterprise.constants import ENTERPRISE_ADMIN_ROLE, ENTERPRISE_LEARNER_ROLE
from enterprise.models import SystemWideEnterpriseRole, SystemWideEnterpriseUserRoleAssignment
from test_utils import FAKE_UUIDS, TEST_USERNAME, APITest, factories


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
class TestEnterpriseCustomerUserReadOnlySerializer(TestCase):
    """
    Tests for EnterpriseCustomerUserReadOnlySerializer.
    """

    def setUp(self):
        """
        Perform operations common for all tests.

        """
        super().setUp()
        self.user_1 = factories.UserFactory()
        self.user_2 = factories.UserFactory()
        self.enterprise_customer_user_1 = factories.EnterpriseCustomerUserFactory(user_id=self.user_1.id)
        self.enterprise_customer_user_2 = factories.EnterpriseCustomerUserFactory(user_id=self.user_2.id)

        self.enterprise_admin_role, _ = SystemWideEnterpriseRole.objects.get_or_create(
            name=ENTERPRISE_ADMIN_ROLE,
        )
        self.enterprise_learner_role, _ = SystemWideEnterpriseRole.objects.get_or_create(
            name=ENTERPRISE_LEARNER_ROLE,
        )

        # Clear all current assignments
        SystemWideEnterpriseUserRoleAssignment.objects.all().delete()

        # Assign both admin and learner roles to the first user
        factories.SystemWideEnterpriseUserRoleAssignmentFactory(
            role=self.enterprise_admin_role,
            user=self.enterprise_customer_user_1.user,
            enterprise_customer=self.enterprise_customer_user_1.enterprise_customer
        )
        factories.SystemWideEnterpriseUserRoleAssignmentFactory(
            role=self.enterprise_learner_role,
            user=self.enterprise_customer_user_1.user,
            enterprise_customer=self.enterprise_customer_user_1.enterprise_customer
        )

        # Assign learner role to the second user
        factories.SystemWideEnterpriseUserRoleAssignmentFactory(
            role=self.enterprise_learner_role,
            user=self.enterprise_customer_user_2.user,
            enterprise_customer=self.enterprise_customer_user_2.enterprise_customer
        )

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
