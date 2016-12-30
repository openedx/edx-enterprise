# -*- coding: utf-8 -*-
"""
Forms to be used in the enterprise djangoapp.
"""
from __future__ import absolute_import, unicode_literals

from logging import getLogger

from edx_rest_api_client.exceptions import HttpClientError, HttpServerError

from django import forms
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db.models.fields import BLANK_CHOICE_DASH
from django.utils.translation import ugettext as _

from enterprise import utils
from enterprise.admin.utils import ValidationMessages, email_or_username__to__email, validate_email_to_link
from enterprise.course_catalog_api import get_all_catalogs
from enterprise.enrollment_api import get_course_details
from enterprise.models import EnterpriseCustomer, EnterpriseCustomerIdentityProvider

logger = getLogger(__name__)  # pylint: disable=invalid-name


class ManageLearnersForm(forms.Form):
    """
    Form to manage learner additions.
    """
    email_or_username = forms.CharField(label=_("Type in Email or Username to link single user"), required=False)
    bulk_upload_csv = forms.FileField(
        label=_("Or upload a CSV to enroll multiple users at once"), required=False,
        help_text=_("The CSV must have a column of email addresses, indicated by the heading 'email' in the first row.")
    )
    course = forms.CharField(
        label=_("Also enroll these learners in this course"), required=False,
        help_text=_("Provide a course ID if enrollment is desired."),
    )
    course_mode = forms.ChoiceField(
        label=_("Course enrollment mode"), required=False,
        choices=BLANK_CHOICE_DASH + [
            ("audit", _("Audit")),
            ("verified", _("Verified")),
            ("professional", _("Professsional Education")),
        ],
    )

    class Modes(object):
        """
        Namespace class for form modes.
        """
        MODE_SINGULAR = "singular"
        MODE_BULK = "bulk"

    class Fields(object):
        """
        Namespace class for field names.
        """
        GENERAL_ERRORS = forms.forms.NON_FIELD_ERRORS

        EMAIL_OR_USERNAME = "email_or_username"
        BULK_UPLOAD = "bulk_upload_csv"
        MODE = "mode"
        COURSE = "course"
        COURSE_MODE = "course_mode"

    class CsvColumns(object):
        """
        Namespace class for CSV column names.
        """
        EMAIL = "email"

    def clean_email_or_username(self):
        """
        Clean email form field

        Returns:
            str: the cleaned value, converted to an email address (or an empty string)
        """
        email_or_username = self.cleaned_data[self.Fields.EMAIL_OR_USERNAME].strip()

        if not email_or_username:
            # The field is blank; we just return the existing blank value.
            return email_or_username

        email = email_or_username__to__email(email_or_username)
        validate_email_to_link(email, email_or_username, ValidationMessages.INVALID_EMAIL_OR_USERNAME)

        return email

    def clean_course(self):
        """
        Verify course ID and retrieve course details.
        """
        course_id = self.cleaned_data[self.Fields.COURSE].strip()
        if not course_id:
            return None
        try:
            return get_course_details(course_id)
        except (HttpClientError, HttpServerError):
            raise ValidationError(ValidationMessages.INVALID_COURSE_ID.format(course_id=course_id))

    def clean(self):
        """
        Clean fields that depend on each other.

        In this case, the form can be used to link single user or bulk link multiple users. These are mutually
        exclusive modes, so this method checks that only one field is passed.
        """
        cleaned_data = super(ManageLearnersForm, self).clean()

        # Here we take values from `data` (and not `cleaned_data`) as we need raw values - field clean methods
        # might "invalidate" the value and set it to None, while all we care here is if it was provided at all or not
        email_or_username = self.data.get(self.Fields.EMAIL_OR_USERNAME, None)
        bulk_upload_csv = self.files.get(self.Fields.BULK_UPLOAD, None)

        if not email_or_username and not bulk_upload_csv:
            raise ValidationError(ValidationMessages.NO_FIELDS_SPECIFIED)

        if email_or_username and bulk_upload_csv:
            raise ValidationError(ValidationMessages.BOTH_FIELDS_SPECIFIED)

        if email_or_username:
            mode = self.Modes.MODE_SINGULAR
        else:
            mode = self.Modes.MODE_BULK

        cleaned_data[self.Fields.MODE] = mode

        # Verify that the selected mode is valid for the given course .
        course_details = self.cleaned_data.get(self.Fields.COURSE)
        if course_details:
            course_mode = self.cleaned_data.get(self.Fields.COURSE_MODE)
            if not course_mode:
                raise ValidationError(ValidationMessages.COURSE_WITHOUT_COURSE_MODE)
            valid_course_modes = course_details["course_modes"]
            if all(course_mode != mode["slug"] for mode in valid_course_modes):
                error = ValidationError(ValidationMessages.COURSE_MODE_INVALID_FOR_COURSE.format(
                    course_mode=course_mode,
                    course_id=course_details["course_id"],
                ))
                raise ValidationError({self.Fields.COURSE_MODE: error})

        return cleaned_data


class EnterpriseCustomerAdminForm(forms.ModelForm):
    """
    Alternate form for the EnterpriseCustomer admin page.

    This form fetches catalog names and IDs from the course catalog API.
    """
    class Meta:
        model = EnterpriseCustomer
        fields = "__all__"

    class Media:
        js = ('enterprise/admin/enterprise_customer.js', )

    def __init__(self, *args, **kwargs):
        """
        Initialize the form.

        Substitute a ChoiceField in for the catalog field that would
        normally be set up as a plain number entry field.
        """
        super(EnterpriseCustomerAdminForm, self).__init__(*args, **kwargs)

        self.fields['catalog'] = forms.ChoiceField(
            choices=self.get_catalog_options(),
            required=False,
            help_text="<a id='catalog-details-link' href='#' target='_blank'"
                      "data-url-template='{catalog_admin_url}'> View catalog details.</a>".format(
                          catalog_admin_url=utils.get_catalog_admin_url_template(),
                      )
        )

    def get_catalog_options(self):
        """
        Retrieve a list of catalog ID and name pairs.

        Once retrieved, these name pairs can be used directly as a value
        for the `choices` argument to a ChoiceField.
        """
        catalogs = get_all_catalogs(self.user)
        # order catalogs by name.
        catalogs = sorted(catalogs, key=lambda catalog: catalog.get('name', '').lower())

        return ((None, _('None'),),) + tuple(
            (catalog['id'], catalog['name'],)
            for catalog in catalogs
        )


class EnterpriseCustomerIdentityProviderAdminForm(forms.ModelForm):
    """
    Alternate form for the EnterpriseCustomerIdentityProvider admin page.

    This form fetches identity providers from lms third_party_auth app.
    If third_party_auth app is not avilable it displays provider_id as a CharField.
    """
    class Meta:
        model = EnterpriseCustomerIdentityProvider
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        """
        Initialize the form.

        Substitutes CharField with TypedChoiceField for the provider_id field.
        """
        super(EnterpriseCustomerIdentityProviderAdminForm, self).__init__(*args, **kwargs)
        idp_choices = utils.get_idp_choices()
        if idp_choices is not None:
            self.fields['provider_id'] = forms.TypedChoiceField(choices=idp_choices)

    def clean(self):
        """
        Final validations of model fields.

        1. Validate that selected site for enterprise customer matches with the selected identity provider's site.
        """
        super(EnterpriseCustomerIdentityProviderAdminForm, self).clean()

        provider_id = self.cleaned_data.get('provider_id', None)
        enterprise_customer = self.cleaned_data.get('enterprise_customer', None)

        if provider_id is None or enterprise_customer is None:
            # field validation for either provider_id or enterprise_customer has already raised
            # a validation error.
            return
        try:
            identity_provider = utils.get_identity_provider(provider_id)
        except ObjectDoesNotExist:
            # This should not happen, as identity providers displayed in drop down are fetched dynamically.
            message = _(
                "Selected Identity Provider does not exist, please contact system administrator for more info.",
            )
            # Log message for debugging
            logger.exception(message)

            raise ValidationError(message)

        if identity_provider and identity_provider.site != enterprise_customer.site:
            raise ValidationError(
                _(
                    "Site ({identity_provider_site}) of selected identity provider does not match with "
                    "enterprise customer's site ({enterprise_customer_site})."
                    "Please either select site with domain '{identity_provider_site}' or update identity provider's "
                    "site to '{enterprise_customer_site}'."
                ).format(
                    enterprise_customer_site=enterprise_customer.site,
                    identity_provider_site=identity_provider.site,
                ),
            )
