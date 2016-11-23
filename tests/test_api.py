# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` api module.
"""

from __future__ import absolute_import, unicode_literals, with_statement

import unittest

import ddt
from faker import Factory as FakerFactory
from pytest import mark

from enterprise.api import get_enterprise_branding_info
from test_utils.factories import EnterpriseCustomerBrandingFactory, EnterpriseCustomerFactory


@mark.django_db
@ddt.ddt
class TestEnterpriseCustomer(unittest.TestCase):
    """
    Tests of the EnterpriseCustomer model.
    """

    def test_enterprise_branding_info(self):
        """
        Test ``get_enterprise_branding_info`` helper method.
        """
        faker = FakerFactory.create()
        customer_uuid = faker.uuid4()
        identity_provider = faker.slug()
        EnterpriseCustomerBrandingFactory(
            id=1,
            enterprise_customer=EnterpriseCustomerFactory(
                uuid=customer_uuid,
                name="QWERTY",
                identity_provider=identity_provider
            ),
            logo='/test.png/'
        )

        self.assertEqual(get_enterprise_branding_info(provider_id=identity_provider).logo, '/test.png/')
        self.assertEqual(get_enterprise_branding_info(provider_id='fake'), None)
