# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` models module.
"""

from __future__ import absolute_import, unicode_literals, with_statement

import unittest

import ddt
import mock
from faker import Factory as FakerFactory
from pytest import mark, raises

from django.core.exceptions import ValidationError
from django.core.files import File
from django.core.files.storage import Storage

from enterprise.models import (EnterpriseCustomer, EnterpriseCustomerBrandingConfiguration, EnterpriseCustomerUser,
                               PendingEnterpriseCustomerUser, logo_path)
from test_utils.factories import (EnterpriseCustomerFactory, EnterpriseCustomerIdentityProviderFactory,
                                  EnterpriseCustomerUserFactory, PendingEnterpriseCustomerUserFactory,
                                  UserDataSharingConsentAuditFactory, UserFactory)


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
class TestUserDataSharingConsentAudit(unittest.TestCase):
    """
    Tests of the UserDataSharingConsent model.
    """
    @ddt.data(
        str, repr
    )
    def test_string_conversion(self, method):
        """
        Test ``UserDataSharingConsentAudit`` conversion to string
        """
        user = UserFactory(email='bob@jones.com')
        enterprise_customer = EnterpriseCustomerFactory(name='EvilCorp')
        ec_user = EnterpriseCustomerUserFactory(user_id=user.id, enterprise_customer=enterprise_customer)
        audit = UserDataSharingConsentAuditFactory(user=ec_user)
        expected_to_str = "<UserDataSharingConsentAudit for bob@jones.com and EvilCorp: not_set>"
        assert expected_to_str == method(audit)


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

    def test_identity_provider(self):
        """
        Test identity_provider property returns correct value without errors.
        """
        faker = FakerFactory.create()
        provider_id = faker.slug()
        customer = EnterpriseCustomerFactory()
        EnterpriseCustomerIdentityProviderFactory(provider_id=provider_id, enterprise_customer=customer)

        assert customer.identity_provider == provider_id  # pylint: disable=no-member

    def test_no_identity_provider(self):
        """
        Test identity_provider property returns correct value without errors.

        Test that identity_provider property does not raise ObjectDoesNotExist and returns None
        if enterprise customer doesn not have an associated identity provider.
        """
        customer = EnterpriseCustomerFactory()
        assert customer.identity_provider is None  # pylint: disable=no-member


@mark.django_db
@ddt.ddt
# TODO: remove suppression when https://github.com/landscapeio/pylint-django/issues/78 is fixed
# pylint: disable=no-member
class TestEnterpriseCustomerUserManager(unittest.TestCase):
    """
    Tests EnterpriseCustomerUserManager.
    """

    @ddt.data(
        "albert.einstein@princeton.edu", "richard.feynman@caltech.edu", "leo.susskind@stanford.edu"
    )
    def test_link_user_existing_user(self, user_email):
        enterprise_customer = EnterpriseCustomerFactory()
        user = UserFactory(email=user_email)
        assert len(EnterpriseCustomerUser.objects.all()) == 0, "Precondition check: no link records should exist"
        assert len(PendingEnterpriseCustomerUser.objects.filter(user_email=user_email)) == 0, \
            "Precondition check: no pending link records should exist"

        EnterpriseCustomerUser.objects.link_user(enterprise_customer, user_email)
        actual_records = EnterpriseCustomerUser.objects.filter(
            enterprise_customer=enterprise_customer, user_id=user.id  # pylint: disable=no-member
        )
        assert len(actual_records) == 1
        assert len(PendingEnterpriseCustomerUser.objects.all()) == 0, "No pending link records should have been created"

    @ddt.data(
        "yoda@jeditemple.net", "luke_skywalker@resistance.org", "darth_vader@empire.com"
    )
    def test_link_user_no_user(self, user_email):
        enterprise_customer = EnterpriseCustomerFactory()

        assert len(EnterpriseCustomerUser.objects.all()) == 0, "Precondition check: no link records should exist"
        assert len(PendingEnterpriseCustomerUser.objects.filter(user_email=user_email)) == 0, \
            "Precondition check: no pending link records should exist"

        EnterpriseCustomerUser.objects.link_user(enterprise_customer, user_email)
        actual_records = PendingEnterpriseCustomerUser.objects.filter(
            enterprise_customer=enterprise_customer, user_email=user_email
        )
        assert len(actual_records) == 1
        assert len(EnterpriseCustomerUser.objects.all()) == 0, "No pending link records should have been created"

    @ddt.data("email1@example.com", "email2@example.com")
    def test_get_link_by_email_linked_user(self, email):
        user = UserFactory(email=email)
        existing_link = EnterpriseCustomerUserFactory(user_id=user.id)
        assert EnterpriseCustomerUser.objects.get_link_by_email(email) == existing_link

    @ddt.data("email1@example.com", "email2@example.com")
    def test_get_link_by_email_pending_link(self, email):
        existing_pending_link = PendingEnterpriseCustomerUserFactory(user_email=email)
        assert EnterpriseCustomerUser.objects.get_link_by_email(email) == existing_pending_link

    @ddt.data("email1@example.com", "email2@example.com")
    def test_get_link_by_email_no_link(self, email):
        assert len(EnterpriseCustomerUser.objects.all()) == 0
        assert len(PendingEnterpriseCustomerUser.objects.all()) == 0
        assert EnterpriseCustomerUser.objects.get_link_by_email(email) is None

    @ddt.data("email1@example.com", "email2@example.com")
    def test_unlink_user_existing_user(self, email):
        other_email = "other_email@example.com"
        user1, user2 = UserFactory(email=email), UserFactory(email=other_email)
        enterprise_customer1, enterprise_customer2 = EnterpriseCustomerFactory(), EnterpriseCustomerFactory()
        EnterpriseCustomerUserFactory(enterprise_customer=enterprise_customer1, user_id=user1.id)
        EnterpriseCustomerUserFactory(enterprise_customer=enterprise_customer1, user_id=user2.id)
        EnterpriseCustomerUserFactory(enterprise_customer=enterprise_customer2, user_id=user1.id)
        assert len(EnterpriseCustomerUser.objects.all()) == 3

        query_method = EnterpriseCustomerUser.objects.filter

        EnterpriseCustomerUser.objects.unlink_user(enterprise_customer1, email)
        # removes what was asked
        assert len(query_method(enterprise_customer=enterprise_customer1, user_id=user1.id)) == 0
        # keeps records of the same user with different EC (though it shouldn't be the case)
        assert len(query_method(enterprise_customer=enterprise_customer2, user_id=user1.id)) == 1
        # keeps records of other users
        assert len(query_method(user_id=user2.id)) == 1

    @ddt.data("email1@example.com", "email2@example.com")
    def test_unlink_user_pending_link(self, email):
        other_email = "other_email@example.com"
        enterprise_customer = EnterpriseCustomerFactory()
        PendingEnterpriseCustomerUserFactory(enterprise_customer=enterprise_customer, user_email=email)
        PendingEnterpriseCustomerUserFactory(enterprise_customer=enterprise_customer, user_email=other_email)
        assert len(PendingEnterpriseCustomerUser.objects.all()) == 2

        query_method = PendingEnterpriseCustomerUser.objects.filter

        EnterpriseCustomerUser.objects.unlink_user(enterprise_customer, email)
        # removes what was asked
        assert len(query_method(enterprise_customer=enterprise_customer, user_email=email)) == 0
        # keeps records of other users
        assert len(query_method(user_email=other_email)) == 1

    @ddt.data("email1@example.com", "email2@example.com")
    def test_unlink_user_existing_user_no_link(self, email):
        user = UserFactory(email=email)
        enterprise_customer = EnterpriseCustomerFactory()
        query_method = EnterpriseCustomerUser.objects.filter

        assert len(query_method(user_id=user.id)) == 0, "Precondition check: link record exists"

        with raises(EnterpriseCustomerUser.DoesNotExist):
            EnterpriseCustomerUser.objects.unlink_user(enterprise_customer, email)

    @ddt.data("email1@example.com", "email2@example.com")
    def test_unlink_user_no_user_no_pending_link(self, email):
        enterprise_customer = EnterpriseCustomerFactory()
        query_method = PendingEnterpriseCustomerUser.objects.filter

        assert len(query_method(user_email=email)) == 0, "Precondition check: link record exists"

        with raises(PendingEnterpriseCustomerUser.DoesNotExist):
            EnterpriseCustomerUser.objects.unlink_user(enterprise_customer, email)


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
        expected_to_str = "<EnterpriseCustomerUser {ID}>: {enterprise_name} - {user_id}".format(
            ID=customer_user_id,
            enterprise_name=customer_user.enterprise_customer.name,
            user_id=user_id
        )
        self.assertEqual(method(customer_user), expected_to_str)

    @ddt.data(
        "albert.einstein@princeton.edu", "richard.feynman@caltech.edu", "leo.susskind@stanford.edu"
    )
    def test_user_property_user_exists(self, email):
        user_instance = UserFactory(email=email)
        enterprise_customer_user = EnterpriseCustomerUserFactory(user_id=user_instance.id)  # pylint: disable=no-member
        assert enterprise_customer_user.user == user_instance  # pylint: disable=no-member

    @ddt.data(1, 42, 1138)
    def test_user_property_user_missing(self, user_id):
        enterprise_customer_user = EnterpriseCustomerUserFactory(user_id=user_id)
        assert enterprise_customer_user.user is None  # pylint: disable=no-member

    @ddt.data(
        "albert.einstein@princeton.edu", "richard.feynman@caltech.edu", "leo.susskind@stanford.edu"
    )
    # TODO: remove suppression when https://github.com/landscapeio/pylint-django/issues/78 is fixed
    # pylint: disable=no-member
    def test_user_email_property_user_exists(self, email):
        user = UserFactory(email=email)
        enterprise_customer_user = EnterpriseCustomerUserFactory(user_id=user.id)
        assert enterprise_customer_user.user_email == email

    # TODO: remove suppression when https://github.com/landscapeio/pylint-django/issues/78 is fixed
    # pylint: disable=no-member
    def test_user_email_property_user_missing(self):
        enterprise_customer_user = EnterpriseCustomerUserFactory(user_id=42)
        assert enterprise_customer_user.user_email is None


@mark.django_db
@ddt.ddt
class TestPendingEnterpriseCustomerUser(unittest.TestCase):
    """
    Tests of the PendingEnterpriseCustomerUser model.
    """

    @ddt.data(
        str, repr
    )
    def test_string_conversion(self, method):
        """
        Test ``EnterpriseCustomerUser`` conversion to string.
        """
        customer_user_id, user_email = 15, "some_email@example.com"
        customer_user = PendingEnterpriseCustomerUserFactory(id=customer_user_id, user_email=user_email)
        expected_to_str = "<PendingEnterpriseCustomerUser {ID}>: {enterprise_name} - {user_email}".format(
            ID=customer_user_id,
            enterprise_name=customer_user.enterprise_customer.name,
            user_email=user_email
        )
        self.assertEqual(method(customer_user), expected_to_str)


@mark.django_db
@ddt.ddt
class TestEnterpriseCustomerBrandingConfiguration(unittest.TestCase):
    """
    Tests of the EnterpriseCustomerBrandingConfiguration model.
    """

    @staticmethod
    def _make_file_mock(name="logo.png", size=240*1024):
        """
        Build file mock.
        """
        file_mock = mock.MagicMock(spec=File, name="FileMock")
        file_mock.name = name
        file_mock.size = size
        return file_mock

    @ddt.data(
        str, repr
    )
    def test_string_conversion(self, method):
        """
        Test ``EnterpriseCustomerUser`` conversion to string.
        """
        file_mock = self._make_file_mock()
        customer_branding_config = EnterpriseCustomerBrandingConfiguration(
            id=1, logo=file_mock, enterprise_customer=EnterpriseCustomerFactory()
        )
        expected_str = "<EnterpriseCustomerBrandingConfiguration {ID}>: {enterprise_name}".format(
            ID=customer_branding_config.id,
            enterprise_name=customer_branding_config.enterprise_customer.name,
        )
        self.assertEqual(method(customer_branding_config), expected_str)

    def test_logo_path(self):
        """
        Test path of image file should be enterprise/branding/<model.id>/<model_id>_logo.<ext>.lower().
        """
        file_mock = self._make_file_mock()
        branding_config = EnterpriseCustomerBrandingConfiguration(
            id=1,
            enterprise_customer=EnterpriseCustomerFactory(),
            logo=file_mock
        )

        storage_mock = mock.MagicMock(spec=Storage, name="StorageMock")
        with mock.patch("django.core.files.storage.default_storage._wrapped", storage_mock):
            path = logo_path(branding_config, branding_config.logo.name)
            self.assertEqual(path, "enterprise/branding/1/1_logo.png")

    def test_branding_configuration_saving_successfully(self):
        """
        Test enterprise customer branding configuration saving successfully.
        """
        storage_mock = mock.MagicMock(spec=Storage, name="StorageMock")
        branding_config_1 = EnterpriseCustomerBrandingConfiguration(
            enterprise_customer=EnterpriseCustomerFactory(),
            logo="test1.png"
        )

        storage_mock.exists.return_value = True
        with mock.patch("django.core.files.storage.default_storage._wrapped", storage_mock):
            branding_config_1.save()
            self.assertEqual(EnterpriseCustomerBrandingConfiguration.objects.count(), 1)

        branding_config_2 = EnterpriseCustomerBrandingConfiguration(
            enterprise_customer=EnterpriseCustomerFactory(),
            logo="test2.png"
        )

        storage_mock.exists.return_value = False
        with mock.patch("django.core.files.storage.default_storage._wrapped", storage_mock):
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
        file_mock = mock.MagicMock(spec=File, name="FileMock")
        file_mock.name = "test1.png"
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
        (False, ".jpg"),
        (False, ".gif"),
        (False, ".bmp"),
        (True, ".png"),
    )
    @ddt.unpack
    def test_image_type(self, valid_image, image_extension):
        """
        Test image type, currently .png is supported in configuration. see apps.py.
        """
        file_mock = mock.MagicMock(spec=File, name="FileMock")
        file_mock.name = "test1" + image_extension
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


@mark.django_db
@ddt.ddt
class TestEnterpriseCustomerIdentityProvider(unittest.TestCase):
    """
    Tests of the EnterpriseCustomerIdentityProvider model.
    """

    @ddt.data(
        str, repr
    )
    def test_string_conversion(self, method):
        """
        Test ``EnterpriseCustomerIdentityProvider`` conversion to string.
        """
        provider_id, enterprise_customer_name = "saml-test", "TestShib"
        enterprise_customer = EnterpriseCustomerFactory(name=enterprise_customer_name)
        ec_idp = EnterpriseCustomerIdentityProviderFactory(
            enterprise_customer=enterprise_customer,
            provider_id=provider_id,
        )

        expected_to_str = "<EnterpriseCustomerIdentityProvider {provider_id}>: {enterprise_name}".format(
            provider_id=provider_id,
            enterprise_name=enterprise_customer_name,
        )
        self.assertEqual(method(ec_idp), expected_to_str)

    @mock.patch("enterprise.models.utils.get_identity_provider")
    def test_provider_name(self, mock_method):
        """
        Test provider_name property returns correct value without errors..
        """
        faker = FakerFactory.create()
        provider_name = faker.name()
        mock_method.return_value.configure_mock(name=provider_name)
        ec_idp = EnterpriseCustomerIdentityProviderFactory()

        assert ec_idp.provider_name == provider_name  # pylint: disable=no-member
