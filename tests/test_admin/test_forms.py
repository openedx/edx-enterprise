# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` admin forms module.
"""
from __future__ import absolute_import, unicode_literals

import json
import unittest

import ddt
import mock
from faker import Factory as FakerFactory
from pytest import mark

from django.core.files import File

from enterprise.admin.forms import (
    EnterpriseCustomerCatalogAdminForm,
    EnterpriseCustomerIdentityProviderAdminForm,
    EnterpriseCustomerReportingConfigAdminForm,
    ManageLearnersForm,
)
from enterprise.admin.utils import ValidationMessages
from test_utils import fake_enrollment_api
from test_utils.factories import (
    EnterpriseCatalogQueryFactory,
    EnterpriseCustomerCatalogFactory,
    EnterpriseCustomerFactory,
    EnterpriseCustomerIdentityProviderFactory,
    EnterpriseCustomerUserFactory,
    PendingEnterpriseCustomerUserFactory,
    SiteFactory,
    UserFactory,
)

FAKER = FakerFactory.create()


@mark.django_db
@ddt.ddt
class TestManageLearnersForm(unittest.TestCase):
    """
    Tests for ManageLearnersForm.
    """

    @staticmethod
    def _make_bound_form(
            email,
            file_attached=False,
            course="",
            course_mode="",
            notify="",
            reason="tests",
            discount=0.0
    ):
        """
        Builds bound ManageLearnersForm.
        """
        form_data = {
            ManageLearnersForm.Fields.EMAIL_OR_USERNAME: email,
            ManageLearnersForm.Fields.COURSE: course,
            ManageLearnersForm.Fields.COURSE_MODE: course_mode,
            ManageLearnersForm.Fields.NOTIFY: notify,
            ManageLearnersForm.Fields.REASON: reason,
            ManageLearnersForm.Fields.DISCOUNT: discount,
        }
        file_data = {}
        if file_attached:
            mock_file = mock.Mock(spec=File)
            mock_file.name = "some_file.csv"
            mock_file.read.return_value = "fake file contents"
            file_data = {ManageLearnersForm.Fields.BULK_UPLOAD: mock_file}

        customer = EnterpriseCustomerFactory()
        return ManageLearnersForm(form_data, file_data, enterprise_customer=customer)

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
        UserFactory(username="user1", email="user1@example.com", id=1)
        UserFactory(username="user2", email="user2@example.com", id=2)

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
        EnterpriseCustomerUserFactory(user_id=user.id)  # pylint: disable=no-member

        form = self._make_bound_form(form_entry)
        assert form.is_valid()
        cleaned_data = form.clean()
        assert cleaned_data[ManageLearnersForm.Fields.EMAIL_OR_USERNAME] == existing_email

    @ddt.data("user1@example.com", "qwe@asd.com",)
    def test_clean_existing_pending_link(self, existing_email):
        PendingEnterpriseCustomerUserFactory(user_email=existing_email)

        form = self._make_bound_form(existing_email)
        assert form.is_valid()
        cleaned_data = form.clean()
        assert cleaned_data[ManageLearnersForm.Fields.EMAIL_OR_USERNAME] == existing_email

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

    @ddt.data(None, "")
    def test_clean_course_empty(self, value):
        form = self._make_bound_form("irrelevant@example.com", course=value)
        assert form.is_valid()
        assert form.cleaned_data[form.Fields.COURSE] is None

    @mock.patch("enterprise.admin.forms.EnrollmentApiClient")
    def test_clean_course_valid(self, enrollment_client):
        instance = enrollment_client.return_value
        instance.get_course_details.side_effect = fake_enrollment_api.get_course_details
        course_id = "course-v1:edX+DemoX+Demo_Course"
        course_details = fake_enrollment_api.COURSE_DETAILS[course_id]
        course_mode = "audit"
        form = self._make_bound_form("irrelevant@example.com", course=course_id, course_mode=course_mode)
        assert form.is_valid()
        assert form.cleaned_data[form.Fields.COURSE] == course_details

    @ddt.data("course-v1:does+not+exist", "invalid_course_id")
    @mock.patch("enterprise.admin.forms.EnrollmentApiClient")
    def test_clean_course_invalid(self, course_id, enrollment_client):
        instance = enrollment_client.return_value
        instance.get_course_details.side_effect = fake_enrollment_api.get_course_details
        form = self._make_bound_form("irrelevant@example.com", course=course_id)
        assert not form.is_valid()
        assert form.errors == {
            form.Fields.COURSE: [ValidationMessages.INVALID_COURSE_ID.format(course_id=course_id)],
        }

    @mock.patch("enterprise.admin.forms.EnrollmentApiClient")
    def test_clean_valid_course_empty_mode(self, enrollment_client):
        instance = enrollment_client.return_value
        instance.get_course_details.side_effect = fake_enrollment_api.get_course_details
        course_id = "course-v1:edX+DemoX+Demo_Course"
        form = self._make_bound_form("irrelevant@example.com", course=course_id, course_mode="")
        assert not form.is_valid()
        assert form.errors == {"__all__": [ValidationMessages.COURSE_WITHOUT_COURSE_MODE]}

    @mock.patch("enterprise.admin.forms.EnrollmentApiClient")
    def test_clean_valid_course_invalid_mode(self, enrollment_client):
        instance = enrollment_client.return_value
        instance.get_course_details.side_effect = fake_enrollment_api.get_course_details
        course_id = "course-v1:edX+DemoX+Demo_Course"
        course_mode = "verified"
        form = self._make_bound_form("irrelevant@example.com", course=course_id, course_mode=course_mode)
        assert not form.is_valid()
        assert form.errors == {
            form.Fields.COURSE_MODE: [ValidationMessages.COURSE_MODE_INVALID_FOR_COURSE.format(
                course_mode=course_mode, course_id=course_id
            )],
        }

    @ddt.unpack
    @ddt.data(
        (0.0, True, False),
        (50.0, True, False),
        (100.0, True, False),
        (-10.0, False, False),
        (101.0, False, False),
        (101.000001, False, True),
        (10.9999993, False, True),
    )
    def test_clean_discount(self, discount, is_valid, is_decimal_error):
        """
        Tests that clean_discount method
        """
        form = self._make_bound_form('irrelevant@example.com', discount=discount)
        if is_valid:
            assert form.is_valid()
            cleaned_data = form.clean()
            assert cleaned_data[ManageLearnersForm.Fields.DISCOUNT] == discount
        else:
            assert not form.is_valid()
            error_message = ValidationMessages.INVALID_DISCOUNT
            if is_decimal_error:
                error_message = 'Ensure that there are no more than 5 decimal places.'
            assert form.errors == {form.Fields.DISCOUNT: [error_message]}

    @ddt.unpack
    @ddt.data(
        ("a thirst for knowledge", "a thirst for knowledge"),
        ("   a thirst for knowledge   ", "a thirst for knowledge"),  # strips spaces
        ("\r\t\n a thirst for knowledge", "a thirst for knowledge"),  # strips spaces
        ("a thirst for knowledge\r\t\n ", "a thirst for knowledge"),  # strips spaces
        ("    ", ""),
    )
    def test_clean_reason(self, reason, expected_reason):
        form = self._make_bound_form("irrelevant@example.com", reason=reason)
        assert form.is_valid()
        cleaned_data = form.clean()
        assert cleaned_data[ManageLearnersForm.Fields.REASON] == expected_reason

    @mock.patch("enterprise.admin.forms.EnrollmentApiClient")
    def test_validate_reason(self, enrollment_client):
        instance = enrollment_client.return_value
        instance.get_course_details.side_effect = fake_enrollment_api.get_course_details
        course_id = "course-v1:edX+DemoX+Demo_Course"
        reason = ""
        form = self._make_bound_form("irrelevant@example.com", course=course_id, reason=reason, course_mode="audit")
        assert not form.is_valid()
        assert form.errors == {
            "__all__": [ValidationMessages.MISSING_REASON]
        }


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
        self.provider_id = FAKER.slug()  # pylint: disable=no-member

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

        error_message = (
            "The site for the selected identity provider "
            "({identity_provider_site}) does not match the site for "
            "this enterprise customer ({enterprise_customer_site}). "
            "To correct this problem, select a site that has a domain "
            "of '{identity_provider_site}', or update the identity "
            "provider to '{enterprise_customer_site}'."
        ).format(
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
        mock_method.return_value = None

        form = EnterpriseCustomerIdentityProviderAdminForm(
            data={"provider_id": self.provider_id, "enterprise_customer": self.enterprise_customer.uuid},
        )
        error_message = (
            "The specified Identity Provider does not exist. For "
            "more information, contact a system administrator."
        )
        # Validate and clean form data
        assert not form.is_valid()
        assert error_message in form.errors["__all__"]

    @mock.patch("enterprise.admin.forms.utils.get_identity_provider")
    @mock.patch("enterprise.admin.forms.saml_provider_configuration")
    @mock.patch('enterprise.admin.forms.reverse')
    @mock.patch("enterprise.admin.forms.utils.get_idp_choices")
    def test_create_new_identity_provider_link(self, mock_idp_choices, mock_url, mock_saml_config, mock_method):
        """
        Test create new identity provider link in help text.
        """
        provider_id = FAKER.slug()  # pylint: disable=no-member
        name = FAKER.name()

        # pylint: disable=invalid-name
        enterprise_customer_identity_provider = EnterpriseCustomerIdentityProviderFactory(
            enterprise_customer=EnterpriseCustomerFactory(site=SiteFactory(domain="site.localhost.com"))
        )
        mock_method.return_value = mock.Mock(pk=1, name=name, provider_id=provider_id)
        mock_saml_config._meta.app_label = 'test_app'
        mock_saml_config._meta.model_name = 'test_model'
        mock_url.return_value = '/test_saml_app/test_saml_model/add/'
        mock_idp_choices.return_value = self.idp_choices
        form = EnterpriseCustomerIdentityProviderAdminForm(
            {
                'provider_id': provider_id,
                'enterprise_customer': self.enterprise_customer
            },
            instance=enterprise_customer_identity_provider
        )
        assert '/test_saml_app/test_saml_model/add/?source=1' in form.fields['provider_id'].help_text
        assert form.fields['provider_id'].choices == list(self.idp_choices)

        # Without provider id information.
        form = EnterpriseCustomerIdentityProviderAdminForm(
            {
                'enterprise_customer': self.enterprise_customer
            },
            instance=None
        )
        assert 'Create a new identity provider' in form.fields['provider_id'].help_text
        assert '/test_saml_app/test_saml_model/add/?source=1' not in form.fields['provider_id'].help_text
        assert form.fields['provider_id'].choices == list(self.idp_choices)

        mock_method.return_value = None
        # Invalid provider id.
        form = EnterpriseCustomerIdentityProviderAdminForm(
            {
                'enterprise_customer': self.enterprise_customer
            },
            instance=enterprise_customer_identity_provider
        )
        assert 'Make sure you have added a valid provider_id' in form.fields['provider_id'].help_text

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


@mark.django_db
class TestEnterpriseCustomerReportingConfigAdminForm(unittest.TestCase):
    """
    Tests for EnterpriseCustomerReportingConfigAdminForm.
    """

    def setUp(self):
        """
        Test set up.
        """
        super(TestEnterpriseCustomerReportingConfigAdminForm, self).setUp()

        self.ent_customer1 = EnterpriseCustomerFactory()
        self.ent_customer2 = EnterpriseCustomerFactory()

        self.ent_catalogs1 = [
            EnterpriseCustomerCatalogFactory(enterprise_customer=self.ent_customer1)
            for _ in range(3)
        ]
        self.ent_catalogs2 = [
            EnterpriseCustomerCatalogFactory(enterprise_customer=self.ent_customer2)
            for _ in range(2)
        ]

        self.form_data = {
            'enterprise_customer': self.ent_customer1.uuid,
            'data_type': 'progress',
            'report_type': 'csv',
            'delivery_method': 'email',
            'frequency': 'daily',
            'hour_of_day': 1,
            'email': 'fake@edx.org',
            'decrypted_password': 'password',
        }

    def test_form_no_catalogs(self):
        """
        Test clean method on form that has no catalogs set
        """
        form = EnterpriseCustomerReportingConfigAdminForm(
            data=self.form_data,
        )
        assert form.is_valid()

    def test_form_catalogs_same_entcustomer_only(self):
        """
        Clean should not throw errors about catalogs if catalogs selected have
        same enterprise customer as reporting config
        """
        self.form_data['enterprise_customer_catalogs'] = self.ent_catalogs1

        form = EnterpriseCustomerReportingConfigAdminForm(
            data=self.form_data,
        )
        assert form.is_valid()

    def test_form_catalogs_different_entcustomer_only(self):
        """
        Clean should throw errors about catalogs if catalogs selected have
        different enterprise customer as reporting config
        """
        self.form_data['enterprise_customer_catalogs'] = self.ent_catalogs2

        form = EnterpriseCustomerReportingConfigAdminForm(
            data=self.form_data,
        )
        assert not form.is_valid()

    def test_form_catalogs_mixed_entcustomer(self):
        """
        Clean should throw errors about catalogs if catalogs selected have a
        mix of enterprise customers, at least one of which matches the
        config reporting object
        """
        self.form_data['enterprise_customer_catalogs'] = (
            self.ent_catalogs1 + self.ent_catalogs2
        )
        form = EnterpriseCustomerReportingConfigAdminForm(
            data=self.form_data,
        )
        assert not form.is_valid()


@ddt.ddt
@mark.django_db
class EnterpriseCustomerCatalogAdminFormTest(unittest.TestCase):
    """
    Tests Different type of utilities methods.
    """
    dummy_content_filter_data = {
        'field': 'value'
    }
    catalog_query_content_filter = {
        "query_field": "query_data"
    }
    form = EnterpriseCustomerCatalogAdminForm

    def setUp(self):
        """
        Test set up.
        """
        super(EnterpriseCustomerCatalogAdminFormTest, self).setUp()
        EnterpriseCatalogQueryFactory(content_filter=self.catalog_query_content_filter)

    @ddt.unpack
    @ddt.data(
        (
            {
                'enterprise_customer_catalogs-1-preview_button': 'Preview',
                'enterprise_customer_catalogs-0-content_filter': json.dumps({'field_0': 'value_0'}),
                'enterprise_customer_catalogs-1-content_filter': json.dumps(dummy_content_filter_data),
                'enterprise_customer_catalogs-2-content_filter': json.dumps({'field_2': 'value_2'}),
                'enterprise_customer_catalogs-1-uuid': 'CFDF8161-5225-4278-9479-9331A6A16C33'
            },
            'CFDF8161-5225-4278-9479-9331A6A16C33'
        ),
        (
            {
                'enterprise_customer_catalogs-0-content_filter': json.dumps({'field_0': 'value_0'}),
                'enterprise_customer_catalogs-1-content_filter': json.dumps(dummy_content_filter_data),
                'enterprise_customer_catalogs-2-content_filter': json.dumps({'field_2': 'value_2'}),
            },
            None
        ),
        (
            {
                'enterprise_customer_catalogs-1-preview_button': 'Preview',
                'enterprise_customer_catalogs-0-content_filter': json.dumps({'field_0': 'value_0'}),
                'enterprise_customer_catalogs-1-content_filter': json.dumps(dummy_content_filter_data),
                'enterprise_customer_catalogs-2-content_filter': json.dumps({'field_2': 'value_2'}),
                'enterprise_customer_catalogs-1-uuid': '3DEC72FD-6BF6-4F8E-91AD-40C119F1BE3B',
                'enterprise_customer_catalogs-2-uuid': '839F392C-CB03-4116-A3D5-41F2FEBF5853'
            },
            '3DEC72FD-6BF6-4F8E-91AD-40C119F1BE3B'
        )
    )
    def test_get_enterprise_customer_catalog_uuid(self, post_data, expected_result):
        assert self.form.get_catalog_preview_uuid(post_data) == expected_result

    @ddt.unpack
    @ddt.data(
        (
            {
                'enterprise_customer_catalogs-1-preview_button': 'Preview',
                'enterprise_customer_catalogs-2-preview_button': 'Preview',
                'enterprise_customer_catalogs-0-content_filter': json.dumps({'field_0': 'value_0'}),
                'enterprise_customer_catalogs-1-content_filter': json.dumps(dummy_content_filter_data),
                'enterprise_customer_catalogs-2-content_filter': json.dumps({'field_2': 'value_2'}),
                'enterprise_customer_catalogs-1-uuid': '3DEC72FD-6BF6-4F8E-91AD-40C119F1BE3B',
                'enterprise_customer_catalogs-2-uuid': '839F392C-CB03-4116-A3D5-41F2FEBF5853'
            },
            None
        )
    )
    def test_get_catalog_with_two_preview_buttons(self, post_data, expected_result):
        assert self.form.get_catalog_preview_uuid(post_data) == expected_result
