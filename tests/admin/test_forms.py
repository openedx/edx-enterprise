# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` admin forms module.
"""
from __future__ import absolute_import, unicode_literals

import random
import unittest

import ddt
import mock
from faker import Factory as FakerFactory
from pytest import mark, raises

from django import forms
from django.core.exceptions import ObjectDoesNotExist
from django.core.files import File

from enterprise.admin.forms import (EnterpriseCustomerAdminForm, EnterpriseCustomerIdentityProviderAdminForm,
                                    ManageLearnersForm)
from enterprise.admin.utils import ValidationMessages
from enterprise.course_catalog_api import NotConnectedToOpenEdX, get_all_catalogs
from test_utils.factories import (EnterpriseCustomerFactory, EnterpriseCustomerUserFactory,
                                  PendingEnterpriseCustomerUserFactory, SiteFactory, UserFactory)

FAKER = FakerFactory.create()


@mark.django_db
@ddt.ddt
class TestManageLearnersForm(unittest.TestCase):
    """
    Tests for ManageLearnersForm.
    """

    @staticmethod
    def _make_bound_form(email, file_attached=False):
        """
        Builds bound ManageLearnersForm.
        """
        form_data = {ManageLearnersForm.Fields.EMAIL_OR_USERNAME: email}
        file_data = {}
        if file_attached:
            mock_file = mock.Mock(spec=File)
            mock_file.name = "some_file.csv"
            mock_file.read.return_value = "fake file contents"
            file_data = {ManageLearnersForm.Fields.BULK_UPLOAD: mock_file}
        return ManageLearnersForm(form_data, file_data)

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
        assert cleaned_data[ManageLearnersForm.Fields.EMAIL_OR_USERNAME] == email

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
        assert cleaned_data[ManageLearnersForm.Fields.EMAIL_OR_USERNAME] == "space@cowboy.com"

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
        assert errors == {ManageLearnersForm.Fields.EMAIL_OR_USERNAME: [
            ValidationMessages.INVALID_EMAIL_OR_USERNAME.format(argument=email)
        ]}

    @ddt.data(None, "")
    def test_clean_empty_email_and_no_file(self, email):
        """
        Tests that a validation error is raised if empty email is passed
        """
        form = self._make_bound_form(email, file_attached=False)
        assert not form.is_valid()
        errors = form.errors
        assert errors == {"__all__": [ValidationMessages.NO_FIELDS_SPECIFIED]}

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
        assert cleaned_data[ManageLearnersForm.Fields.EMAIL_OR_USERNAME] == expected_email

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
        error_message = ValidationMessages.USER_ALREADY_REGISTERED.format(
            email=existing_email, ec_name=existing_record.enterprise_customer.name
        )
        assert errors == {ManageLearnersForm.Fields.EMAIL_OR_USERNAME: [error_message]}

    @ddt.data("user1@example.com", "qwe@asd.com",)
    def test_clean_existing_pending_link(self, existing_email):
        existing_record = PendingEnterpriseCustomerUserFactory(user_email=existing_email)

        form = self._make_bound_form(existing_email)
        assert not form.is_valid()
        errors = form.errors
        error_message = ValidationMessages.USER_ALREADY_REGISTERED.format(
            email=existing_email, ec_name=existing_record.enterprise_customer.name
        )
        assert errors == {ManageLearnersForm.Fields.EMAIL_OR_USERNAME: [error_message]}

    def test_clean_both_username_and_file(self):
        form = self._make_bound_form("irrelevant@example.com", file_attached=True)

        assert not form.is_valid()
        assert form.errors == {"__all__": [ValidationMessages.BOTH_FIELDS_SPECIFIED]}

    @ddt.data(None, "")
    def test_clean_no_username_no_file(self, empty):
        form = self._make_bound_form(empty, file_attached=False)

        assert not form.is_valid()
        assert form.errors == {"__all__": [ValidationMessages.NO_FIELDS_SPECIFIED]}

    def test_clean_username_no_file(self):
        form = self._make_bound_form("irrelevant@example.com", file_attached=False)
        assert form.is_valid()
        assert form.cleaned_data[form.Fields.MODE] == form.Modes.MODE_SINGULAR

    @ddt.data(None, "")
    def test_clean_no_username_file(self, empty):
        form = self._make_bound_form(empty, file_attached=True)
        assert form.is_valid()
        assert form.cleaned_data[form.Fields.MODE] == form.Modes.MODE_BULK


class TestEnterpriseCustomerAdminForm(unittest.TestCase):
    """
    Tests for EnterpriseCustomerAdminForm.
    """

    def setUp(self):
        """
        Test set up.
        """
        super(TestEnterpriseCustomerAdminForm, self).setUp()
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


@mark.django_db
class TestEnterpriseCustomerIdentityProviderAdminForm(unittest.TestCase):
    """
    Tests for EnterpriseCustomerIdentityProviderAdminForm.
    """

    def setUp(self):
        """
        Test set up.
        """
        super(TestEnterpriseCustomerIdentityProviderAdminForm, self).setUp()
        self.idp_choices = (("saml-idp1", "SAML IdP 1"), ('saml-idp2', "SAML IdP 2"))

        self.first_site = SiteFactory(domain="first.localhost.com")
        self.second_site = SiteFactory(domain="second.localhost.com")
        self.enterprise_customer = EnterpriseCustomerFactory(site=self.first_site)
        self.provider_id = FAKER.slug()

    def test_no_idp_choices(self):
        """
        Test that a CharField is displayed when get_idp_choices returns None.
        """
        with mock.patch("enterprise.admin.forms.utils.get_idp_choices", mock.Mock(return_value=None)):
            form = EnterpriseCustomerIdentityProviderAdminForm()
            assert not hasattr(form.fields['provider_id'], 'choices')

    def test_with_idp_choices(self):
        """
        Test that a TypedChoiceField is displayed when get_idp_choices returns choice tuples.
        """
        with mock.patch("enterprise.admin.forms.utils.get_idp_choices", mock.Mock(return_value=self.idp_choices)):
            form = EnterpriseCustomerIdentityProviderAdminForm()
            assert hasattr(form.fields['provider_id'], 'choices')
            assert form.fields['provider_id'].choices == list(self.idp_choices)

    @mock.patch("enterprise.admin.forms.utils.get_identity_provider")
    def test_error_if_ec_and_idp_site_does_not_match(self, mock_method):
        """
        Test error message when enterprise customer's site and identity provider's site are not same.

        Test validation error message when the site of selected identity provider does not match with
        enterprise customer's site.
        """
        mock_method.return_value = mock.Mock(site=self.second_site)

        form = EnterpriseCustomerIdentityProviderAdminForm(
            data={"provider_id": self.provider_id, "enterprise_customer": self.enterprise_customer.uuid},
        )

        error_message = "Site ({identity_provider_site}) of selected identity provider does not match with " \
                        "enterprise customer's site ({enterprise_customer_site}).Please either select site with " \
                        "domain '{identity_provider_site}' or update identity provider's site to " \
                        "'{enterprise_customer_site}'.".format(
                            enterprise_customer_site=self.first_site,
                            identity_provider_site=self.second_site,
                        )
        # Validate and clean form data
        assert not form.is_valid()
        assert error_message in form.errors["__all__"]

    @mock.patch("enterprise.admin.forms.utils.get_identity_provider")
    def test_error_if_identity_provider_does_not_exist(self, mock_method):
        """
        Test error message when identity provider does not exist.

        Test validation error when selected identity provider does not exists in the system.
        """
        mock_method.side_effect = ObjectDoesNotExist

        form = EnterpriseCustomerIdentityProviderAdminForm(
            data={"provider_id": self.provider_id, "enterprise_customer": self.enterprise_customer.uuid},
        )
        error_message = "Selected Identity Provider does not exist, please contact system administrator for more info."

        # Validate and clean form data
        assert not form.is_valid()
        assert error_message in form.errors["__all__"]

    @mock.patch("enterprise.admin.forms.utils.get_identity_provider")
    def test_clean_runs_without_errors(self, mock_method):
        """
        Test clean method on form runs without any errors.

        Test that form's clean method runs fine in situations where a previous error on some field has already
        raised validation errors.
        """
        mock_method.return_value = mock.Mock(site=self.first_site)

        form = EnterpriseCustomerIdentityProviderAdminForm(
            data={"provider_id": self.provider_id},
        )
        error_message = "This field is required."

        # Validate and clean form data
        assert not form.is_valid()
        assert error_message in form.errors['enterprise_customer']

    @mock.patch("enterprise.admin.forms.utils.get_identity_provider")
    def test_no_errors(self, mock_method):
        """
        Test clean method on form runs without any errors.

        Test that form's clean method runs fine when there are not errors or missing fields.
        """
        mock_method.return_value = mock.Mock(site=self.first_site)

        form = EnterpriseCustomerIdentityProviderAdminForm(
            data={"provider_id": self.provider_id, "enterprise_customer": self.enterprise_customer.uuid},
        )

        # Validate and clean form data
        assert form.is_valid()
