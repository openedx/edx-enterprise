# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` serializer module.
"""

from __future__ import absolute_import, unicode_literals

from pytest import mark

from enterprise.api.v1.serializers import EnterpriseCustomerUserEntitlementSerializer
from test_utils import APITest, factories


@mark.django_db
class TestEnterpriseCustomerUserEntitlementSerializer(APITest):
    """
    Tests for enterprise API serializers.
    """

    def setUp(self):
        """
        Perform operations common for all tests.

        Populate data base for api testing.
        """
        super(TestEnterpriseCustomerUserEntitlementSerializer, self).setUp()

        self.instance = factories.EnterpriseCustomerEntitlementFactory.create()
        self.validated_data = {"entitlements": [1, 2, 3]}

        self.serializer = EnterpriseCustomerUserEntitlementSerializer(
            {"entitlements": [1, 2, 3, 4, 5]}
        )

    def test_update(self):
        """
        Test update method of EnterpriseCustomerUserEntitlementSerializer.

        Verify that update for EnterpriseCustomerUserEntitlementSerializer returns
        successfully without making any changes.
        """
        with self.assertNumQueries(0):
            self.serializer.update(self.instance, self.validated_data)

    def test_create(self):
        """
        Test create method of EnterpriseCustomerUserEntitlementSerializer.

        Verify that create for EnterpriseCustomerUserEntitlementSerializer returns
        successfully without making any changes.
        """
        with self.assertNumQueries(0):
            self.serializer.create(self.validated_data)
