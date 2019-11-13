# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` serializer module.
"""

from __future__ import absolute_import, unicode_literals

import json

import ddt
from pytest import mark
from rest_framework.reverse import reverse

from django.conf import settings
from django.contrib.auth.models import Permission

from enterprise.api.v1.serializers import ImmutableStateSerializer
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
        super(TestImmutableStateSerializer, self).setUp()
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
        super(TestEnterpriseCustomerUserWriteSerializer, cls).setUpClass()
        cls.ent_user_link_url = settings.TEST_SERVER + reverse('enterprise-learner-list')
        cls.permission = Permission.objects.get(name='Can add Enterprise Customer Learner')
        cls.enterprise_uuids = FAKE_UUIDS[:4]
        for enterprise_uuid in cls.enterprise_uuids:
            factories.EnterpriseCustomerFactory(uuid=enterprise_uuid)

    def setUp(self):
        """
        Perform operations common to all tests.
        """
        super(TestEnterpriseCustomerUserWriteSerializer, self).setUp()
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
        expected_inactive_enterprises = list(set(self.enterprise_uuids) - set([active_enterprise]))
        data['enterprise_customer'] = active_enterprise
        data['active'] = True
        self._link_learner_to_enterprise(data)

        response = self.client.get(self.ent_user_link_url)
        response_json = json.loads(response.content)

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
