# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` serializer module.
"""

from __future__ import absolute_import, unicode_literals

import ddt
from pytest import mark
from rest_framework.reverse import reverse

from django.conf import settings
from django.contrib.auth.models import Permission
from django.test import override_settings

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

    @ddt.data(
        (TEST_USERNAME, 201),
        ('non-existing-username', 400),
    )
    @ddt.unpack
    @override_settings(ECOMMERCE_SERVICE_WORKER_USERNAME=TEST_USERNAME)
    def test_validate_username(self, username, expected_status_code):
        """
        Success for POSTing with users (determined by username) depends on whether the user exists.
        """
        self.user.is_staff = True
        self.user.save()
        permission = Permission.objects.get(name='Can add Enterprise Customer Learner')
        self.user.user_permissions.add(permission)
        factories.EnterpriseCustomerFactory(uuid=FAKE_UUIDS[0])
        data = {
            'enterprise_customer': FAKE_UUIDS[0],
            'username': username,
        }

        response = self.client.post(settings.TEST_SERVER + reverse('enterprise-learner-list'), data=data)
        assert response.status_code == expected_status_code
        response = self.load_json(response.content)
        if expected_status_code == 201:
            self.assertDictEqual(data, response)
