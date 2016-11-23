# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` admin forms module.
"""
from __future__ import absolute_import, unicode_literals

import random
import unittest

import ddt
import mock
from pytest import mark, raises

from django import forms

from enterprise.admin.forms import EnterpriseCustomerAdminForm, ManageLearnersForm
from enterprise.course_catalog_api import NotConnectedToOpenEdX, get_all_catalogs
from test_utils.factories import EnterpriseCustomerUserFactory, PendingEnterpriseCustomerUserFactory, UserFactory


@mark.django_db
@ddt.ddt
class TestManageLearnersForm(unittest.TestCase):
    """
    Tests for ManageLearnersForm.
    """

    @staticmethod
    def _make_bound_form(email):
        """
        Builds bound ManageLearnersForm.
        """
        form_data = {"email": email}
        return ManageLearnersForm(form_data)

    @ddt.data(
        "qwe@asd.com", "email1@example.org", "john.t.kirk@starfleet.gov"
    )
    def test_clean_valid_email(self, email):
        """
        Tests that valid emails are kept while cleaning email field
        """
        form = self._make_bound_form(email)
        assert form.is_valid()
        cleaned_data = form.clean()
        assert cleaned_data["email"] == email

    @ddt.data(
        "  space@cowboy.com  ", "\t\n\rspace@cowboy.com \r\n\t",
    )
    def test_clean_valid_email_strips_spaces(self, email):
        """
        Tests that valid emails are kept while cleaning email field
        """
        form = self._make_bound_form(email)
        assert form.is_valid()
        cleaned_data = form.clean()
        assert cleaned_data["email"] == "space@cowboy.com"

    @ddt.data(
        "12345", "email1@", "@example.com"
    )
    def test_clean_invalid_email(self, email):
        """
        Tests that invalid emails cause form validation errors
        """
        form = self._make_bound_form(email)
        assert not form.is_valid()
        errors = form.errors
        assert errors == {"email": ["{} does not appear to be a valid email or known username".format(email)]}

    @ddt.data(None, "")
    def test_clean_empty_email(self, email):
        """
        Tests that a validation error is raised if empty email is passed
        """
        form = self._make_bound_form(email)
        assert not form.is_valid()
        errors = form.errors
        assert errors == {"email": ["This field is required."]}

    @ddt.unpack
    @ddt.data(
        ("user1", "user1@example.com"),
        (" user1 ", "user1@example.com"),  # strips spaces
        ("\r\t\n user1", "user1@example.com"),  # strips spaces
        ("user1\r\t\n ", "user1@example.com"),  # strips spaces
        ("user2", "user2@example.com"),
    )
    def test_clean_existing_username(self, username, expected_email):
        UserFactory(username="user1", email="user1@example.com")
        UserFactory(username="user2", email="user2@example.com")

        form = self._make_bound_form(username)
        assert form.is_valid()
        cleaned_data = form.clean()
        assert cleaned_data["email"] == expected_email

    @ddt.unpack
    @ddt.data(
        ("user1", "user1", "user1@example.com"),  # match by username
        ("user1@example.com", "user1", "user1@example.com"),  # match by email
        ("flynn", "flynn", "flynn@en.com"),  # match by username - alternative email,
    )
    def test_clean_user_already_linked(self, form_entry, existing_username, existing_email):
        user = UserFactory(username=existing_username, email=existing_email)
        existing_record = EnterpriseCustomerUserFactory(user_id=user.id)  # pylint: disable=no-member

        form = self._make_bound_form(form_entry)
        assert not form.is_valid()
        errors = form.errors
        error_message = "User with email {email} is already registered with Enterprise Customer {ec_name}".format(
            email=existing_email, ec_name=existing_record.enterprise_customer.name
        )
        assert errors == {"email": [error_message]}

    @ddt.data("user1@example.com", "qwe@asd.com",)
    def test_clean_existing_pending_link(self, existing_email):
        existing_record = PendingEnterpriseCustomerUserFactory(user_email=existing_email)

        form = self._make_bound_form(existing_email)
        assert not form.is_valid()
        errors = form.errors
        error_message = "User with email {email} is already registered with Enterprise Customer {ec_name}".format(
            email=existing_email, ec_name=existing_record.enterprise_customer.name
        )
        assert errors == {"email": [error_message]}


class TestEnterpriseCustomerAdminForm(unittest.TestCase):
    """
    Tests for EnterpriseCustomerAdminForm.
    """

    def setUp(self):
        """
        Test set up.
        """
        super(TestEnterpriseCustomerAdminForm, self).setUp()
        self.idp_choices_mock = mock.Mock()
        patcher = mock.patch("enterprise.admin.forms.utils.get_idp_choices", self.idp_choices_mock)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.catalog_id = random.randint(2, 1000000)
        self.patch_enterprise_customer_user()
        self.addCleanup(self.unpatch_enterprise_customer_user)

    @staticmethod
    def patch_enterprise_customer_user():
        """
        Set the class-level form user to None.
        """
        EnterpriseCustomerAdminForm.user = None

    @staticmethod
    def unpatch_enterprise_customer_user():
        """
        Set the form to its original state.
        """
        delattr(EnterpriseCustomerAdminForm, 'user')  # pylint: disable=literal-used-as-attribute

    @mock.patch('enterprise.admin.forms.get_all_catalogs')
    def test_no_idp_choices(self, mocked_method):
        mocked_method.return_value = []
        self.idp_choices_mock.return_value = None
        form = EnterpriseCustomerAdminForm()
        assert not hasattr(form.fields['identity_provider'], 'choices')

    @mock.patch('enterprise.admin.forms.get_all_catalogs')
    def test_with_idp_choices(self, mocked_method):
        mocked_method.return_value = []
        choices = (('idp1', 'idp1'), ('idp2', 'idp2'))
        self.idp_choices_mock.return_value = choices
        form = EnterpriseCustomerAdminForm()
        assert hasattr(form.fields['identity_provider'], 'choices')
        assert form.fields['identity_provider'].choices == list(choices)

    @mock.patch('enterprise.admin.forms.get_all_catalogs')
    def test_interface_displays_selected_option(self, mock_method):
        mock_method.return_value = [
            {
                "id": self.catalog_id,
                "name": "My Catalog"
            },
            {
                "id": 1,
                "name": "Other catalog!"
            }
        ]
        form = EnterpriseCustomerAdminForm()
        assert isinstance(form.fields['catalog'], forms.ChoiceField)
        assert form.fields['catalog'].choices == [
            (None, 'None'),
            (self.catalog_id, 'My Catalog'),
            (1, 'Other catalog!'),
        ]

    @mock.patch('enterprise.course_catalog_api.get_catalog_api_client')
    @mock.patch('enterprise.course_catalog_api.CatalogIntegration')
    @mock.patch('enterprise.course_catalog_api.get_edx_api_data')
    def test_with_mocked_get_edx_data(self, mocked_get_edx_data, *args):  # pylint: disable=unused-argument
        mocked_get_edx_data.return_value = [
            {
                "id": self.catalog_id,
                "name": "My Catalog"
            },
            {
                "id": 1,
                "name": "Other catalog!"
            }
        ]
        form = EnterpriseCustomerAdminForm()
        assert isinstance(form.fields['catalog'], forms.ChoiceField)
        assert form.fields['catalog'].choices == [
            (None, 'None'),
            (self.catalog_id, 'My Catalog'),
            (1, 'Other catalog!'),
        ]

    @mock.patch('enterprise.course_catalog_api.CatalogIntegration')
    @mock.patch('enterprise.course_catalog_api.get_edx_api_data')
    def test_raise_error_missing_course_discovery_api(self, *args):  # pylint: disable=unused-argument
        message = 'To get a catalog API client, this package must be installed in an OpenEdX environment.'
        with raises(NotConnectedToOpenEdX) as excinfo:
            get_all_catalogs(None)
        assert message == str(excinfo.value)

    @mock.patch('enterprise.course_catalog_api.course_discovery_api_client')
    @mock.patch('enterprise.course_catalog_api.get_edx_api_data')
    def test_raise_error_missing_catalog_integration(self, *args):  # pylint: disable=unused-argument
        message = 'To get a CatalogIntegration object, this package must be installed in an OpenEdX environment.'
        with raises(NotConnectedToOpenEdX) as excinfo:
            get_all_catalogs(None)
        assert message == str(excinfo.value)

    @mock.patch('enterprise.course_catalog_api.CatalogIntegration')
    @mock.patch('enterprise.course_catalog_api.course_discovery_api_client')
    def test_raise_error_missing_get_edx_api_data(self, *args):  # pylint: disable=unused-argument
        message = 'To parse a catalog API response, this package must be installed in an OpenEdX environment.'
        with raises(NotConnectedToOpenEdX) as excinfo:
            get_all_catalogs(None)
        assert message == str(excinfo.value)
