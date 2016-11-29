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
from test_utils.factories import (EnterpriseCustomerBrandingFactory, EnterpriseCustomerFactory,
                                  EnterpriseCustomerIdentityProviderFactory)


@mark.django_db
@ddt.ddt
class TestEnterpriseCustomer(unittest.TestCase):
    """
    Tests of the EnterpriseCustomer model.
    """

    def test_enterprise_branding_info(self):
        """
        Test `get_enterprise_branding_info` helper method.
        """
        faker = FakerFactory.create()
        provider_id = faker.slug()
        customer = EnterpriseCustomerFactory()
        EnterpriseCustomerIdentityProviderFactory(provider_id=provider_id, enterprise_customer=customer)
        EnterpriseCustomerBrandingFactory(
            enterprise_customer=customer,
            logo='/test.png/'
        )

        self.assertEqual(get_enterprise_branding_info(provider_id=provider_id).logo, '/test.png/')
        self.assertEqual(get_enterprise_branding_info(provider_id='fake'), None)
