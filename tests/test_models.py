# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` models module.
"""

from __future__ import absolute_import, unicode_literals, with_statement

import unittest

import ddt
import mock
from faker import Factory as FakerFactory
from pytest import mark

from django.core.exceptions import ValidationError
from django.core.files import File
from django.core.files.storage import Storage
from django.contrib.sites.models import Site

from enterprise.models import EnterpriseCustomer, EnterpriseCustomerBrandingConfiguration, logo_path
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

    def test_site_association(self):
        """
        Test ``EnterpriseCustomer`` conversion to string.
        """
        faker = FakerFactory.create()
        customer_uuid = faker.uuid4()
        EnterpriseCustomerFactory(uuid=customer_uuid)

        customer = EnterpriseCustomer.objects.get(uuid=customer_uuid)  # pylint: disable=no-member
        site = Site.objects.get(domain="example.com")

        self.assertEqual(customer.site, site)
        self.assertListEqual([customer], list(site.enterprise_customers.all()))


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


@mark.django_db
@ddt.ddt
class TestEnterpriseCustomerBrandingConfiguration(unittest.TestCase):
    """
    Tests of the EnterpriseCustomerBrandingConfiguration model.
    """

    def test_logo_path(self):
        """
        Test path of image file should be enterprise/branding/<model.id>/<model_id>_logo.<ext>.lower().
        """
        file_mock = mock.MagicMock(spec=File, name='FileMock')
        file_mock.name = 'test1.png'
        file_mock.size = 240 * 1024
        branding_config = EnterpriseCustomerBrandingConfiguration(
            id=1,
            enterprise_customer=EnterpriseCustomerFactory(),
            logo=file_mock
        )

        storage_mock = mock.MagicMock(spec=Storage, name='StorageMock')
        with mock.patch('django.core.files.storage.default_storage._wrapped', storage_mock):
            path = logo_path(branding_config, branding_config.logo.name)
            self.assertEqual(path, 'enterprise/branding/1/1_logo.png')

    def test_branding_configuration_saving_successfully(self):
        """
        Test enterprise customer branding configuration saving successfully.
        """
        storage_mock = mock.MagicMock(spec=Storage, name='StorageMock')
        branding_config_1 = EnterpriseCustomerBrandingConfiguration(
            enterprise_customer=EnterpriseCustomerFactory(),
            logo='test1.png'
        )

        storage_mock.exists.return_value = True
        with mock.patch('django.core.files.storage.default_storage._wrapped', storage_mock):
            branding_config_1.save()
            self.assertEqual(EnterpriseCustomerBrandingConfiguration.objects.count(), 1)

        branding_config_2 = EnterpriseCustomerBrandingConfiguration(
            enterprise_customer=EnterpriseCustomerFactory(),
            logo='test2.png'
        )

        storage_mock.exists.return_value = False
        with mock.patch('django.core.files.storage.default_storage._wrapped', storage_mock):
            branding_config_2.save()
            self.assertEqual(EnterpriseCustomerBrandingConfiguration.objects.count(), 2)

    @ddt.data(
        (False, 350 * 1024),
        (False, 251 * 1024),
        (False, 250 * 1024),
        (True, 2 * 1024),
        (True, 249 * 1024),
    )
    @ddt.unpack
    def test_image_size(self, valid_image, image_size):
        """
        Test image size, image_size < (250 * 1024) e.g. 250kb. See apps.py.
        """
        file_mock = mock.MagicMock(spec=File, name='FileMock')
        file_mock.name = 'test1.png'
        file_mock.size = image_size
        branding_configuration = EnterpriseCustomerBrandingConfiguration(
            enterprise_customer=EnterpriseCustomerFactory(),
            logo=file_mock
        )

        if not valid_image:
            with self.assertRaises(ValidationError):
                branding_configuration.full_clean()
        else:
            branding_configuration.full_clean()  # exception here will fail the test

    @ddt.data(
        (False, '.jpg'),
        (False, '.gif'),
        (False, '.bmp'),
        (True, '.png'),
    )
    @ddt.unpack
    def test_image_type(self, valid_image, image_extension):
        """
        Test image type, currently .png is supported in configuration. see apps.py.
        """
        file_mock = mock.MagicMock(spec=File, name='FileMock')
        file_mock.name = 'test1' + image_extension
        file_mock.size = 240 * 1024
        branding_configuration = EnterpriseCustomerBrandingConfiguration(
            enterprise_customer=EnterpriseCustomerFactory(),
            logo=file_mock
        )

        if not valid_image:
            with self.assertRaises(ValidationError):
                branding_configuration.full_clean()
        else:
            branding_configuration.full_clean()  # exception here will fail the test
