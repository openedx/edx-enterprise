# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` utility functions.
"""
from __future__ import absolute_import, unicode_literals

import os
import unittest

import ddt
import mock
import six
from faker import Factory as FakerFactory
from pytest import mark

from django.test import override_settings

from enterprise import utils
from enterprise.models import (EnterpriseCourseEnrollment, EnterpriseCustomer, EnterpriseCustomerBrandingConfiguration,
                               EnterpriseCustomerIdentityProvider, EnterpriseCustomerUser, UserDataSharingConsentAudit)
from enterprise.utils import consent_necessary_for_course, disable_for_loaddata, get_all_field_names
from test_utils.factories import (EnterpriseCustomerFactory, EnterpriseCustomerUserFactory,
                                  UserDataSharingConsentAuditFactory, UserFactory)


def mock_get_available_idps(idps):
    """
    Mock method for get_available_idps.
    """
    def _():
        """
        mock function for get_available_idps.
        """
        idp_list = []
        for idp in idps:
            mock_idp = mock.Mock()
            mock_idp.configure_mock(provider_id=idp, name=idp)
            idp_list.append(mock_idp)
        return idp_list
    return _


@ddt.ddt
@mark.django_db
class TestUtils(unittest.TestCase):
    """
    Tests for utility functions.
    """
    @staticmethod
    def get_magic_name(value):
        """
        Return value suitable for __name__ attribute.

        For python2, __name__ must be str, while for python3 it must be unicode (as there are no str at all).

        Arguments:
            value basestring: string to "convert"

        Returns:
            str or unicode
        """
        return str(value) if six.PY2 else value

    def test_get_idp_choices(self):
        """
        Test get_idp_choices returns correct options for choice field or returns None if
        thirdParty_auth is not installed.
        """
        options = utils.get_idp_choices()
        self.assertIsNone(options)
        expected_list = [('', '-'*7), ('test1', 'test1'), ('test2', 'test2')]

        with mock.patch('enterprise.utils.Registry') as mock_registry:
            mock_registry.enabled = mock_get_available_idps(['test1', 'test2'])

            choices = utils.get_idp_choices()
            self.assertListEqual(choices, expected_list)

    def test_get_identity_provider(self):
        """
        Test get_identity_provider returns correct value.
        """
        faker = FakerFactory.create()
        name = faker.name()
        provider_id = faker.slug()

        # test that get_identity_provider returns None if third_party_auth is not available.
        identity_provider = utils.get_identity_provider(provider_id=provider_id)
        assert identity_provider is None

        # test that get_identity_provider does not return None if third_party_auth is  available.
        with mock.patch('enterprise.utils.Registry') as mock_registry:
            mock_registry.get.return_value.configure_mock(name=name, provider_id=provider_id)
            identity_provider = utils.get_identity_provider(provider_id=provider_id)
            assert identity_provider is not None

    @ddt.unpack
    @ddt.data(
        (
            EnterpriseCustomer,
            [
                "enterprisecustomeruser",
                "pendingenterprisecustomeruser",
                "branding_configuration",
                "enterprise_customer_identity_provider",
                "enterprise_customer_entitlements",
                "created",
                "modified",
                "uuid",
                "name",
                "catalog",
                "active",
                "site",
                "enable_data_sharing_consent",
                "enforce_data_sharing_consent",
            ]
        ),
        (
            EnterpriseCustomerUser,
            [
                "userdatasharingconsentaudit",
                "enterprise_enrollments",
                "id",
                "created",
                "modified",
                "enterprise_customer",
                "user_id",
            ]
        ),
        (
            EnterpriseCustomerBrandingConfiguration,
            [
                "id",
                "created",
                "modified",
                "enterprise_customer",
                "logo"
            ]
        ),
        (
            EnterpriseCustomerIdentityProvider,
            [
                "id",
                "created",
                "modified",
                "enterprise_customer",
                "provider_id"
            ]
        ),
    )
    def test_get_all_field_names(self, model, expected_fields):
        actual_field_names = get_all_field_names(model)
        assert actual_field_names == expected_fields

    @ddt.data(True, False)
    def test_disable_for_loaddata(self, raw):
        signal_handler_mock = mock.MagicMock()
        signal_handler_mock.__name__ = self.get_magic_name("Irrelevant")
        wrapped_handler = disable_for_loaddata(signal_handler_mock)

        wrapped_handler(raw=raw)

        assert signal_handler_mock.called != raw

    @mock.patch('enterprise.utils.add_lookup')
    def test_patch_path(self, lookup_patch):
        utils.patch_mako_lookup()
        assert lookup_patch.call_args[0][0] == 'main'
        assert os.path.isdir(lookup_patch.call_args[0][1])
        assert lookup_patch.call_args[1] == {}

    @ddt.data(
        ("", ""),
        (
            "localhost:18387/api/v1/",
            "localhost:18387/admin/catalogs/catalog/{catalog_id}/change/",
        ),
        (
            "http://localhost:18387/api/v1/",
            "http://localhost:18387/admin/catalogs/catalog/{catalog_id}/change/",
        ),
        (
            "https://prod-site-discovery.example.com/api/v1/",
            "https://prod-site-discovery.example.com/admin/catalogs/catalog/{catalog_id}/change/",
        ),
        (
            "https://discovery-site.subdomain.example.com/api/v1/",
            "https://discovery-site.subdomain.example.com/admin/catalogs/catalog/{catalog_id}/change/",
        ),
    )
    @ddt.unpack
    def test_catalog_admin_url_template(self, catalog_api_url, expected_url):
        """
        Validate that `get_catalog_admin_url_template` utility functions
        returns catalog admin page url template.

        Arguments:
            catalog_api_url (str): course catalog api url coming from DDT data decorator.
            expected_url (str): django admin catalog details page url coming from DDT data decorator.
        """
        with override_settings(COURSE_CATALOG_API_URL=catalog_api_url):
            url = utils.get_catalog_admin_url_template()
            assert url == expected_url

    @ddt.data(
        (7, "", ""),
        (
            7,
            "localhost:18387/api/v1/",
            "localhost:18387/admin/catalogs/catalog/7/change/",
        ),
        (
            7,
            "http://localhost:18387/api/v1/",
            "http://localhost:18387/admin/catalogs/catalog/7/change/",
        ),
        (
            7,
            "https://prod-site-discovery.example.com/api/v1/",
            "https://prod-site-discovery.example.com/admin/catalogs/catalog/7/change/",
        ),
        (
            7,
            "https://discovery-site.subdomain.example.com/api/v1/",
            "https://discovery-site.subdomain.example.com/admin/catalogs/catalog/7/change/",
        ),
    )
    @ddt.unpack
    def test_catalog_admin_url(self, catalog_id, catalog_api_url, expected_url):
        """
        Validate that `get_catalog_admin_url` utility functions returns catalog admin page url.

        Arguments:
            catalog_id (int): catalog id coming from DDT data decorator.
            catalog_api_url (str): course catalog api url coming from DDT data decorator.
            expected_url (str): django admin catalog details page url coming from DDT data decorator.
        """
        with override_settings(COURSE_CATALOG_API_URL=catalog_api_url):
            url = utils.get_catalog_admin_url(catalog_id)
            assert url == expected_url

    @ddt.data(
        (True, True, EnterpriseCustomer.AT_ENROLLMENT, False),
        (None, True, EnterpriseCustomer.AT_ENROLLMENT, True),
        (True, False, EnterpriseCustomer.AT_ENROLLMENT, False),
        (False, False, EnterpriseCustomer.AT_ENROLLMENT, False),
        (None, True, EnterpriseCustomer.AT_LOGIN, True),
        (False, False, EnterpriseCustomer.AT_LOGIN, False),
    )
    @ddt.unpack
    def test_consent_necessary_for_course(
            self,
            consent_provided_state,
            ec_consent_enabled,
            ec_consent_enforcement,
            expected_result
    ):
        user = UserFactory()
        enterprise_customer = EnterpriseCustomerFactory(
            enable_data_sharing_consent=ec_consent_enabled,
            enforce_data_sharing_consent=ec_consent_enforcement,
        )
        enterprise_user = EnterpriseCustomerUserFactory(
            user_id=user.id,
            enterprise_customer=enterprise_customer
        )
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        enrollment = EnterpriseCourseEnrollment.objects.create(
            enterprise_customer_user=enterprise_user,
            consent_granted=consent_provided_state,
            course_id=course_id
        )
        assert consent_necessary_for_course(user, course_id) is expected_result
        account_consent = UserDataSharingConsentAuditFactory(
            user=enterprise_user,
            state=UserDataSharingConsentAudit.ENABLED,
        )
        assert consent_necessary_for_course(user, course_id) is False
        account_consent.delete()  # pylint: disable=no-member
        enrollment.delete()
        assert consent_necessary_for_course(user, course_id) is False
