# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` utility functions.
"""
from __future__ import absolute_import, unicode_literals

import sys
import unittest

import ddt
import mock

from enterprise import utils
from enterprise.models import EnterpriseCustomer, EnterpriseCustomerBrandingConfiguration, EnterpriseCustomerUser
from enterprise.utils import get_all_field_names


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
            mock_idp.configure_mock(idp_slug=idp, name=idp)
            idp_list.append(mock_idp)
        return idp_list
    return _


class MockThirdPartyAuth(object):
    """
    Mock class to stub out third_party_auth package for testing.
    """
    saved_state = {
        'third_party_auth': None,
        'third_party_auth.models': None,
    }

    def __init__(self, providers):
        """
        initialize list of providers, this is the list queryset will return.
        """
        self.providers = providers

    def __enter__(self):
        """
        Save existing package reference, and mock third_party_auth package.
        """
        self.saved_state['third_party_auth'] = sys.modules.get('third_party_auth')
        self.saved_state['third_party_auth.models'] = sys.modules.get('third_party_auth.models')

        sys.modules['third_party_auth'] = mock.Mock()
        sys.modules['third_party_auth.models'] = mock.Mock(
            SAMLProviderConfig=mock_saml_provider_config(self.providers),
        )

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Restore third_party_auth package references.
        """
        sys.modules['third_party_auth'] = self.saved_state['third_party_auth']
        sys.modules['third_party_auth.models'] = self.saved_state['third_party_auth.models']


def mock_saml_provider_config(providers):
    """
    get mock class for SAMLProviderConfig model.
    """
    class SAMLProviderConfig(object):
        """
        mock class for SAMLProviderConfig.
        """
        objects = mock.Mock(
            current_set=mock.Mock(return_value=mock.Mock(
                filter=mock.Mock(
                    return_value=mock.Mock(all=mock.Mock(
                        return_value=providers
                    ))
                )
            ))
        )
    return SAMLProviderConfig


@ddt.ddt
class TestUtils(unittest.TestCase):
    """
    Tests for utility functions.
    """
    def test_get_idp_choices(self):
        """
        Test get_idp_choices returns correct options for choice field or returns None if
        thirdParty_auth is not installed.
        """
        options = utils.get_idp_choices()
        self.assertIsNone(options)
        expected_list = [('', '-'*7), ('test1', 'test1'), ('test2', 'test2')]

        with mock.patch('enterprise.utils.get_available_idps', mock_get_available_idps(['test1', 'test2'])):
            choices = utils.get_idp_choices()
            self.assertListEqual(choices, expected_list)

        available_providers = mock_get_available_idps(['test1', 'test2'])()

        with MockThirdPartyAuth(available_providers):
            self.assertListEqual(utils.get_idp_choices(), expected_list)

    def test_get_available_idps(self):
        """
        Test get_available_idps returns correct value or raises a ValueError if
        thirdParty_auth is not installed.
        """
        with self.assertRaises(ValueError):
            utils.get_available_idps()

        expected_list = ['test1', 'test2']

        with MockThirdPartyAuth(expected_list):
            self.assertListEqual(utils.get_available_idps(), expected_list)

    @ddt.unpack
    @ddt.data(
        (EnterpriseCustomer, [
            "enterprisecustomeruser", "pendingenterprisecustomeruser", "branding_configuration", "created", "modified",
            "uuid", "name", "catalog", "active", "identity_provider", "site"
        ]),
        (EnterpriseCustomerUser, ["id", "created", "modified", "enterprise_customer", "user_id"]),
        (EnterpriseCustomerBrandingConfiguration, ["id", "created", "modified", "enterprise_customer", "logo"]),
    )
    def test_get_all_field_names(self, model, expected_fields):
        actual_field_names = get_all_field_names(model)
        assert actual_field_names == expected_fields
