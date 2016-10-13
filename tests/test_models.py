# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` models module.
"""

from __future__ import absolute_import, unicode_literals

import unittest

import ddt
from faker import Factory as FakerFactory
from pytest import mark

from enterprise.models import EnterpriseCustomer
from test_utils.factories import EnterpriseCustomerFactory, EnterpriseCustomerUserFactory


@mark.django_db
class TestEnterpriseCustomerManager(unittest.TestCase):
    """
    Tests for enterprise customer manager.
    """

    def tearDown(self):
        super(TestEnterpriseCustomerManager, self).tearDown()
        # A bug in pylint-django: https://github.com/landscapeio/pylint-django/issues/53
        # Reports violation on this line: "Instance of 'Manager' has no 'all' member"
        EnterpriseCustomer.objects.all().delete()  # pylint: disable=no-member

    def test_active_customers_get_queryset_returns_only_active(self):
        """
        Test that get_queryset on custom model manager returns only active customers.
        """
        customer1 = EnterpriseCustomerFactory(active=True)
        customer2 = EnterpriseCustomerFactory(active=True)
        inactive_customer = EnterpriseCustomerFactory(active=False)

        active_customers = EnterpriseCustomer.active_customers.all()
        self.assertTrue(all(customer.active for customer in active_customers))
        self.assertIn(customer1, active_customers)
        self.assertIn(customer2, active_customers)
        self.assertNotIn(inactive_customer, active_customers)


@mark.django_db
@ddt.ddt
class TestEnterpriseCustomer(unittest.TestCase):
    """
    Tests of the EnterpriseCustomer model.
    """

    @ddt.data(
        str, repr
    )
    def test_string_conversion(self, method):
        """
        Test ``EnterpriseCustomer`` conversion to string.
        """
        faker = FakerFactory.create()
        customer_uuid = faker.uuid4()
        customer = EnterpriseCustomerFactory(uuid=customer_uuid, name="QWERTY")
        expected_to_str = "<{class_name} {customer_uuid}: {name}>".format(
            class_name=EnterpriseCustomer.__name__,
            customer_uuid=customer_uuid,
            name=customer.name
        )
        self.assertEqual(method(customer), expected_to_str)


@mark.django_db
@ddt.ddt
class TestEnterpriseCustomerUser(unittest.TestCase):
    """
    Tests of the EnterpriseCustomerUser model.
    """

    @ddt.data(
        str, repr
    )
    def test_string_conversion(self, method):
        """
        Test ``EnterpriseCustomerUser`` conversion to string.
        """
        customer_user_id, user_id = 15, 12
        customer_user = EnterpriseCustomerUserFactory(id=customer_user_id, user_id=user_id)
        expected_to_str = "<EnterpriseCustomerUser {ID}: {customer_name} - {user_id}>".format(
            ID=customer_user_id,
            customer_name=customer_user.enterprise_customer.name,
            user_id=user_id
        )
        self.assertEqual(method(customer_user), expected_to_str)
