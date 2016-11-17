# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` admin forms module.
"""
from __future__ import absolute_import, unicode_literals

import unittest

import ddt
import mock
from pytest import mark

from enterprise.admin.forms import EnterpriseCustomerForm, ManageLearnersForm
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


class TestEnterpriseCustomerForm(unittest.TestCase):
    """
    Tests for EnterpriseCustomerForm.
    """

    def setUp(self):
        """
        Test set up.
        """
        super(TestEnterpriseCustomerForm, self).setUp()
        self.idp_choices_mock = mock.Mock()
        patcher = mock.patch("enterprise.admin.forms.utils.get_idp_choices", self.idp_choices_mock)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_no_idp_choices(self):
        self.idp_choices_mock.return_value = None
        form = EnterpriseCustomerForm()
        assert not hasattr(form.fields['identity_provider'], 'choices')

    def test_with_idp_choices(self):
        choices = (('idp1', 'idp1'), ('idp2', 'idp2'))
        self.idp_choices_mock.return_value = choices
        form = EnterpriseCustomerForm()
        assert hasattr(form.fields['identity_provider'], 'choices')
        assert form.fields['identity_provider'].choices == list(choices)
