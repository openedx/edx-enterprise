# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` api module.
"""

from __future__ import absolute_import, unicode_literals, with_statement

import unittest

import ddt
from faker import Factory as FakerFactory
from pytest import mark

from enterprise.api import get_enterprise_branding_info_by_ec_uuid, get_enterprise_branding_info_by_provider_id
from test_utils.factories import (EnterpriseCustomerBrandingFactory, EnterpriseCustomerFactory,
                                  EnterpriseCustomerIdentityProviderFactory)


@mark.django_db
@ddt.ddt
class TestEnterpriseCustomer(unittest.TestCase):
    """
    Tests of the EnterpriseCustomer model.
    """
    def setUp(self):
        """
        Set up test environment.
        """
        super(TestEnterpriseCustomer, self).setUp()
        faker = FakerFactory.create()
        self.provider_id = faker.slug()
        self.uuid = faker.uuid4()
        self.customer = EnterpriseCustomerFactory(uuid=self.uuid)
        EnterpriseCustomerIdentityProviderFactory(provider_id=self.provider_id, enterprise_customer=self.customer)

    def test_enterprise_branding_info_by_provider_id(self):
        """
        Test `get_enterprise_branding_info_by_provider_id` helper method.
        """
        EnterpriseCustomerBrandingFactory(
            enterprise_customer=self.customer,
            logo='/test_1.png/'
        )
        self.assertEqual(get_enterprise_branding_info_by_provider_id(), None)
        self.assertEqual(get_enterprise_branding_info_by_provider_id(provider_id=self.provider_id).logo, '/test_1.png/')
        self.assertEqual(get_enterprise_branding_info_by_provider_id(provider_id='fake'), None)

    def test_enterprise_branding_info_by_ec_uuid(self):
        """
        Test `get_enterprise_branding_info_by_ec_uuid` helper method.
        """
        EnterpriseCustomerBrandingFactory(
            enterprise_customer=self.customer,
            logo='/test_2.png/'
        )

        self.assertEqual(get_enterprise_branding_info_by_ec_uuid(), None)
        self.assertEqual(get_enterprise_branding_info_by_ec_uuid(ec_uuid=self.uuid).logo, '/test_2.png/')
        self.assertEqual(get_enterprise_branding_info_by_ec_uuid(ec_uuid=FakerFactory.create().uuid4()), None)
