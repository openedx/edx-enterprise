"""
Tests for the `edx-enterprise` admin forms module.
"""

import json
import unittest
from datetime import date, timedelta
from unittest import mock

import ddt
from faker import Factory as FakerFactory
from pytest import mark

from django.core.files import File
from django.test import TestCase

from enterprise.admin.forms import (
    AdminNotificationForm,
    EnterpriseCustomerCatalogAdminForm,
    EnterpriseCustomerIdentityProviderAdminForm,
    EnterpriseCustomerReportingConfigAdminForm,
    ManageLearnersDataSharingConsentForm,
    ManageLearnersForm,
    SystemWideEnterpriseUserRoleAssignmentForm,
)
from enterprise.admin.utils import ValidationMessages
from enterprise.constants import ENTERPRISE_ADMIN_ROLE
from enterprise.models import EnterpriseCustomer, EnterpriseCustomerReportingConfiguration, SystemWideEnterpriseRole
from test_utils import TEST_PGP_KEY, factories, fake_enrollment_api
from test_utils.factories import (
    AdminNotificationFactory,
    EnterpriseCatalogQueryFactory,
    EnterpriseCustomerCatalogFactory,
    EnterpriseCustomerFactory,
    EnterpriseCustomerIdentityProviderFactory,
    EnterpriseCustomerUserFactory,
    PendingEnterpriseCustomerUserFactory,
    SiteFactory,
    SystemWideEnterpriseUserRoleAssignmentFactory,
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
            file_has_courses=False,
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
            if file_has_courses:
                mock_file.read.return_value = b'email,course_id\nfake@example.com,course-v1:edX+DemoX_Demo_Course'
            else:
                mock_file.read.return_value = b'email\nfake@example.com'
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
        EnterpriseCustomerUserFactory(user_id=user.id)

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

    @mock.patch("enterprise.models.EnterpriseCatalogApiClient")
    @mock.patch("enterprise.api_client.lms.EnrollmentApiClient")
    def test_clean_course_valid(self, enrollment_client, enterprise_catalog_client):
        enrollment_instance = enrollment_client.return_value
        enrollment_instance.get_course_details.side_effect = fake_enrollment_api.get_course_details
        enterprise_catalog_instance = enterprise_catalog_client.return_value
        enterprise_catalog_instance.enterprise_contains_content_items.return_value = {
            'contains_content_items': True,
        }
        course_id = "course-v1:edX+DemoX+Demo_Course"
        course_details = fake_enrollment_api.COURSE_DETAILS[course_id]
        course_mode = "audit"
        form = self._make_bound_form("irrelevant@example.com", course=course_id, course_mode=course_mode)
        assert form.is_valid()
        assert form.cleaned_data[form.Fields.COURSE] == course_details

    @ddt.data("course-v1:does+not+exist", "invalid_course_id")
    @mock.patch("enterprise.api_client.lms.EnrollmentApiClient")
    def test_clean_course_invalid(self, course_id, enrollment_client):
        instance = enrollment_client.return_value
        instance.get_course_details.side_effect = fake_enrollment_api.get_course_details
        form = self._make_bound_form("irrelevant@example.com", course=course_id)
        assert not form.is_valid()
        assert form.errors == {
            form.Fields.COURSE: [ValidationMessages.INVALID_COURSE_ID.format(course_id=course_id)],
        }

    @mock.patch("enterprise.models.EnterpriseCatalogApiClient")
    @mock.patch("enterprise.api_client.lms.EnrollmentApiClient")
    def test_clean_valid_course_empty_mode(self, enrollment_client, enterprise_catalog_client):
        enrollment_instance = enrollment_client.return_value
        enrollment_instance.get_course_details.side_effect = fake_enrollment_api.get_course_details
        enterprise_catalog_instance = enterprise_catalog_client.return_value
        enterprise_catalog_instance.enterprise_contains_content_items.return_value = {
            'contains_content_items': True,
        }
        course_id = "course-v1:edX+DemoX+Demo_Course"
        form = self._make_bound_form("irrelevant@example.com", course=course_id, course_mode="")
        assert not form.is_valid()
        assert form.errors == {"__all__": [ValidationMessages.COURSE_WITHOUT_COURSE_MODE]}

    @mock.patch("enterprise.models.EnterpriseCatalogApiClient")
    @mock.patch("enterprise.api_client.lms.EnrollmentApiClient")
    def test_clean_valid_course_invalid_mode(self, enrollment_client, enterprise_catalog_client):
        enrollment_instance = enrollment_client.return_value
        enrollment_instance.get_course_details.side_effect = fake_enrollment_api.get_course_details
        enterprise_catalog_instance = enterprise_catalog_client.return_value
        enterprise_catalog_instance.enterprise_contains_content_items.return_value = {
            'contains_content_items': True,
        }
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

    @ddt.data(
        {
            'course': 'fake-course-id',
            'course_mode': None,
            'reason': None,
            'error': ValidationMessages.BOTH_COURSE_FIELDS_SPECIFIED,
            'file_has_courses': True,
        },
        {
            'course': None,
            'course_mode': None,
            'reason': None,
            'error': ValidationMessages.COURSE_WITHOUT_COURSE_MODE,
            'file_has_courses': True,
        },
        {
            'course': None,
            'course_mode': 'audit',
            'reason': None,
            'error': ValidationMessages.MISSING_REASON,
            'file_has_courses': True,
        },
        {
            'course': None,
            'course_mode': 'audit',
            'reason': 'tests',
            'error': None,
            'file_has_courses': True,
        },
        {
            'course': 'fake-course-id',
            'course_mode': 'audit',
            'reason': 'tests',
            'error': None,
            'file_has_courses': False,
        },
    )
    @ddt.unpack
    @mock.patch("enterprise.models.EnterpriseCatalogApiClient")
    @mock.patch("enterprise.api_client.lms.EnrollmentApiClient")
    def test_validate_bulk_upload_fields(
            self,
            enrollment_client,
            enterprise_catalog_client,
            course,
            course_mode,
            reason,
            error,
            file_has_courses,
    ):
        enrollment_instance = enrollment_client.return_value
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        enrollment_instance.get_course_details.return_value = fake_enrollment_api.get_course_details(course_id)
        enterprise_catalog_instance = enterprise_catalog_client.return_value
        enterprise_catalog_instance.enterprise_contains_content_items.return_value = {
            'contains_content_items': True,
        }
        form = self._make_bound_form(
            "",
            course=course,
            course_mode=course_mode,
            reason=reason,
            file_attached=True,
            file_has_courses=file_has_courses,
        )
        if not error:
            assert form.is_valid()
        else:
            assert not form.is_valid()
            assert form.errors == {
                "__all__": [error]
            }

    @mock.patch("enterprise.models.EnterpriseCatalogApiClient")
    @mock.patch("enterprise.api_client.lms.EnrollmentApiClient")
    def test_validate_reason(self, enrollment_client, enterprise_catalog_client):
        enrollment_instance = enrollment_client.return_value
        enrollment_instance.get_course_details.side_effect = fake_enrollment_api.get_course_details
        enterprise_catalog_instance = enterprise_catalog_client.return_value
        enterprise_catalog_instance.enterprise_contains_content_items.return_value = {
            'contains_content_items': True,
        }
        course_id = "course-v1:edX+DemoX+Demo_Course"
        reason = ""
        form = self._make_bound_form("irrelevant@example.com", course=course_id, reason=reason, course_mode="audit")
        assert not form.is_valid()
        assert form.errors == {
            "__all__": [ValidationMessages.MISSING_REASON]
        }


@mark.django_db
@ddt.ddt
class TestManageLearnersDataSharingConsentForm(unittest.TestCase):
    """
    Tests for ManageLearnersDataSharingConsentForm.
    """

    def setUp(self):
        super().setUp()
        self.enterprise_customer = EnterpriseCustomerFactory()

    def _make_bound_form(
            self,
            email_or_username="dummy@example.com",
            course_id="course-v1:edX+DemoX+Demo_Course"
    ):
        """
        Builds bound ManageLearnersDataSharingConsentForm.
        """
        form_data = {
            ManageLearnersForm.Fields.EMAIL_OR_USERNAME: email_or_username,
            ManageLearnersForm.Fields.COURSE: course_id,
        }
        return ManageLearnersDataSharingConsentForm(form_data, enterprise_customer=self.enterprise_customer)

    @staticmethod
    def assert_valid_form(form, field_name, expected_field_value):
        """
        Assert that form is valid.
        """
        assert form.is_valid()
        cleaned_data = form.clean()
        assert cleaned_data[field_name] == expected_field_value

    @mock.patch("enterprise.api_client.lms.EnrollmentApiClient")
    def test_clean(self, enrollment_client):
        """
        Test clean_email_or_username and clean_course methods.
        """
        instance = enrollment_client.return_value
        instance.get_course_details.side_effect = fake_enrollment_api.get_course_details
        username = "user_linked"
        course_id = "course-v1:edX+DemoX+Demo_Course"
        user = UserFactory(username=username, email='user_linked@example.com')
        EnterpriseCustomerUserFactory(enterprise_customer=self.enterprise_customer, user_id=user.id)

        with mock.patch.object(EnterpriseCustomer, 'catalog_contains_course') as mock_catalog_contains_course:
            mock_catalog_contains_course.return_value = True
            form = self._make_bound_form(email_or_username=username, course_id=course_id)
            assert form.is_valid()
            cleaned_data = form.clean()
            assert cleaned_data[ManageLearnersDataSharingConsentForm.Fields.COURSE] == course_id
            assert cleaned_data[ManageLearnersDataSharingConsentForm.Fields.EMAIL_OR_USERNAME] == user.email


@mark.django_db
class TestEnterpriseCustomerIdentityProviderAdminForm(unittest.TestCase):
    """
    Tests for EnterpriseCustomerIdentityProviderAdminForm.
    """

    def setUp(self):
        """
        Test set up.
        """
        super().setUp()
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
            data={"provider_id": self.provider_id, "enterprise_customer": self.enterprise_customer.uuid,
                  "enterprise_customer_identity_providers-TOTAL_FORMS": 0},
        )

        # Validate and clean form data
        assert form.is_valid()

    @mock.patch("enterprise.admin.forms.utils.get_identity_provider")
    def test_error_if_multiple_default_providers(self, mock_method):
        """
        Test clean method on form runs without any errors.

        Test that form's clean method runs fine when there are not errors or missing fields.
        """
        mock_method.return_value = mock.Mock(site=self.first_site)

        form = EnterpriseCustomerIdentityProviderAdminForm(
            data={"provider_id": self.provider_id, "enterprise_customer": self.enterprise_customer.uuid,
                  "enterprise_customer_identity_providers-TOTAL_FORMS": 2,
                  "enterprise_customer_identity_providers-0-default_provider": "on",
                  "enterprise_customer_identity_providers-1-default_provider": "on",
                  },
        )

        error_message = "Please select only one default provider."

        assert not form.is_valid()
        assert error_message in form.errors["__all__"]

    @mock.patch("enterprise.admin.forms.utils.get_identity_provider")
    def test_error_if_no_default_provider(self, mock_method):
        """
        Test clean method on form runs without any errors.

        Test that form's clean method runs fine when there are not errors or missing fields.
        """
        mock_method.return_value = mock.Mock(site=self.first_site)

        form = EnterpriseCustomerIdentityProviderAdminForm(
            data={"provider_id": self.provider_id, "enterprise_customer": self.enterprise_customer.uuid,
                  "enterprise_customer_identity_providers-TOTAL_FORMS": 2,
                  "enterprise_customer_identity_providers-0-default_provider": "",
                  "enterprise_customer_identity_providers-1-default_provider": "",
                  },
        )

        error_message = "Please select one default provider."

        assert not form.is_valid()
        assert error_message in form.errors["__all__"]

    @mock.patch("enterprise.admin.forms.utils.get_identity_provider")
    def test_no_errors_for_one_default_provider(self, mock_method):
        """
        Test clean method on form runs without any errors.

        Test that form's clean method runs fine when there are not errors or missing fields.
        """
        mock_method.return_value = mock.Mock(site=self.first_site)

        form = EnterpriseCustomerIdentityProviderAdminForm(
            data={"provider_id": self.provider_id, "enterprise_customer": self.enterprise_customer.uuid,
                  "enterprise_customer_identity_providers-TOTAL_FORMS": 2,
                  "enterprise_customer_identity_providers-0-default_provider": "on",
                  "enterprise_customer_identity_providers-1-default_provider": "",
                  },
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
        super().setUp()

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
            'data_type': 'progress_v3',
            'report_type': 'csv',
            'delivery_method': 'email',
            'frequency': 'daily',
            'hour_of_day': 1,
            'email': 'fake@edx.org',
            'decrypted_password': 'password',
            'enable_compression': True,
        }

    def test_form_valid_delivery_method(self):
        """
        Test clean method on form that check delivery method validity
        """
        enterprise_customer = factories.EnterpriseCustomerFactory(name="GriffCo")
        config = EnterpriseCustomerReportingConfiguration.objects.create(
            enterprise_customer=enterprise_customer,
            active=True,
            delivery_method='email',
            email='test@edx.org',
            decrypted_password='test_password',
            day_of_month=1,
            hour_of_day=1,
        )
        form_data = self.form_data.copy()
        form_data['delivery_method'] = 'email'
        form = EnterpriseCustomerReportingConfigAdminForm(
            instance=config,
            data=form_data,
        )
        assert form.is_valid()

        form_data = self.form_data.copy()
        form_data['delivery_method'] = 'sftp'
        form = EnterpriseCustomerReportingConfigAdminForm(
            instance=config,
            data=form_data,
        )

        assert not form.is_valid()

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

    def test_invalid_pgp_key(self):
        """
        Clean should throw errors about invalid pgp keys
        """
        self.form_data['pgp_encryption_key'] = 'invalid-pgp-key'
        form = EnterpriseCustomerReportingConfigAdminForm(
            data=self.form_data,
        )
        assert not form.is_valid()

    def test_valid_pgp_key(self):
        """
        Clean should accept valid pgp keys.

        Also, user can choose to not provide a PGP key. Error should not be raised in this case.
        """
        self.form_data['pgp_encryption_key'] = TEST_PGP_KEY
        form = EnterpriseCustomerReportingConfigAdminForm(
            data=self.form_data,
        )
        assert form.is_valid()

        # Empty value for PGP key is allowed
        self.form_data['pgp_encryption_key'] = ''
        form = EnterpriseCustomerReportingConfigAdminForm(
            data=self.form_data,
        )
        assert form.is_valid()

    def test_validate_manual_reporting(self):
        """
        Verify that manual reporting validation works as exepcted.

        Only enterprises enabled for manual reporting can create reporting configuration.
        """
        report_config_data = dict(self.form_data, data_type=EnterpriseCustomerReportingConfiguration.DATA_TYPE_GRADE)
        form = EnterpriseCustomerReportingConfigAdminForm(
            data=report_config_data,
        )
        assert not form.is_valid()
        errors = form.errors
        message = '"{data_type}" data type is not supported for enterprise customer "{enterprise_customer.name}". Please select a different data type.'.format(  # pylint: disable=line-too-long
            enterprise_customer=self.ent_customer1,
            data_type=EnterpriseCustomerReportingConfiguration.DATA_TYPE_GRADE,
        )
        assert errors == {'data_type': [message]}


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
        super().setUp()
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


class SystemWideEnterpriseUserRoleAssignmentFormTest(TestCase):
    """
    Tests that this form appropriately filters the set of enterprise_customers to choose from.
    """
    @classmethod
    def setUpTestData(cls):
        cls.enterprise_customer = EnterpriseCustomerFactory.create()
        cls.other_enterprise_customer = EnterpriseCustomerFactory.create()

        cls.user = UserFactory.create()
        cls.enterprise_admin_role, _ = SystemWideEnterpriseRole.objects.get_or_create(
            name=ENTERPRISE_ADMIN_ROLE,
        )
        cls.role_assignment = SystemWideEnterpriseUserRoleAssignmentFactory.create(
            user=cls.user,
            role=cls.enterprise_admin_role,
        )

        _ = EnterpriseCustomerUserFactory.create(
            user_id=cls.user.id,
            enterprise_customer=cls.enterprise_customer,
        )
        super().setUpTestData()

    def test_enterprise_customer_field_contains_only_linked_customers(self):
        form = SystemWideEnterpriseUserRoleAssignmentForm(
            instance=self.role_assignment,
        )

        actual_customers = list(form.fields['enterprise_customer'].queryset)
        expected_customers = [self.enterprise_customer]
        assert expected_customers == actual_customers

    def test_form_without_instance_references_no_enterprise_customers(self):
        form = SystemWideEnterpriseUserRoleAssignmentForm(
            data={
                'user': self.user.email,
                'role': ENTERPRISE_ADMIN_ROLE,
            }
        )

        actual_customers = list(form.fields['enterprise_customer'].queryset)
        expected_customers = []
        assert expected_customers == actual_customers


@mark.django_db
class TestAdminNotificationForm(unittest.TestCase):
    """
    Tests for AdminNotificationForm.
    """

    def setUp(self):
        """
        Test set up.
        """
        super().setUp()
        self.form_data = {
            'title': 'Notification Banner title for admin',
            'text': 'Notification Banner text for admin',
            'start_date': date.today(),
            'expiration_date': date.today(),
        }

    def test_form_valid(self):
        """
        Test clean method on form that has no errors
        """
        form = AdminNotificationForm(
            data=self.form_data,
        )
        assert form.is_valid()

    def test_overlap_date_form_error(self):
        """
        Test clean method on form that has errors due to overlap of start and expiration date
        """
        AdminNotificationFactory(start_date=date.today(), expiration_date=date.today())
        form = AdminNotificationForm(
            data=self.form_data,
        )
        assert not form.is_valid()

    def test_expiration_date_error(self):
        """
        Test clean method on form that has errors for expiration date coming before start date
        """
        form_data = self.form_data
        form_data['expiration_date'] = date.today() - timedelta(days=2)
        form = AdminNotificationForm(
            data=form_data,
        )
        assert not form.is_valid()
