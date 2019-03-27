# -*- coding: utf-8 -*-
"""
Forms to be used in the enterprise djangoapp.
"""
from __future__ import absolute_import, unicode_literals

from logging import getLogger

from edx_rbac.admin.forms import UserRoleAssignmentAdminForm
from edx_rest_api_client.exceptions import HttpClientError, HttpServerError

from django import forms
from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.db.models.fields import BLANK_CHOICE_DASH
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _

from enterprise import utils
from enterprise.admin.utils import (
    ProgramStatuses,
    ValidationMessages,
    email_or_username__to__email,
    get_course_runs_from_program,
    split_usernames_and_emails,
    validate_email_to_link,
)
from enterprise.api_client.discovery import CourseCatalogApiClient
from enterprise.api_client.lms import EnrollmentApiClient
from enterprise.models import (
    EnterpriseCustomer,
    EnterpriseCustomerCatalog,
    EnterpriseCustomerIdentityProvider,
    EnterpriseCustomerReportingConfiguration,
    EnterpriseFeatureUserRoleAssignment,
    SystemWideEnterpriseUserRoleAssignment,
)
from enterprise.utils import MultipleProgramMatchError

try:
    from third_party_auth.models import SAMLProviderConfig as saml_provider_configuration
except ImportError:
    saml_provider_configuration = None

logger = getLogger(__name__)  # pylint: disable=invalid-name


class ManageLearnersForm(forms.Form):
    """
    Form to manage learner additions.
    """
    email_or_username = forms.CharField(
        label=_(
            "To add a single learner, enter an email address or username."),
        required=False)
    bulk_upload_csv = forms.FileField(
        label=_(
            "To add multiple learners, upload a .csv file that contains a "
            "column of email addresses."
        ),
        required=False,
        help_text=_(
            "The .csv file must have a column of email addresses, indicated "
            "by the heading 'email' in the first row."
        )
    )
    course = forms.CharField(
        label=_("Enroll these learners in this course"), required=False,
        help_text=_("To enroll learners in a course, enter a course ID."),
    )
    program = forms.CharField(
        label=_("Or enroll these learners in this program"), required=False,
        help_text=_(
            "To enroll learners in a program, enter a program name or ID.")
    )
    course_mode = forms.ChoiceField(
        label=_("Course enrollment track"), required=False,
        choices=BLANK_CHOICE_DASH + [
            ("audit", _("Audit")),
            ("verified", _("Verified")),
            ("professional", _("Professional Education")),
            ("no-id-professional", _("Professional Education (no ID)")),
            ("credit", _("Credit")),
            ("honor", _("Honor")),
        ],
    )

    class NotificationTypes(object):
        """
        Namespace class for notification types
        """
        BY_EMAIL = 'by_email'
        NO_NOTIFICATION = 'do_not_notify'
        DEFAULT = getattr(settings, 'DEFAULT_ENTERPRISE_NOTIFICATION_MECHANISM', BY_EMAIL)

    notify_on_enrollment = forms.ChoiceField(
        label=_("Notify learners of enrollment"),
        choices=[
            (NotificationTypes.BY_EMAIL, _("Send email")),
            (NotificationTypes.NO_NOTIFICATION, _("Do not notify")),
        ],
        initial=NotificationTypes.DEFAULT,
        required=False,
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
        PROGRAM = "program"
        NOTIFY = "notify_on_enrollment"

    class CsvColumns(object):
        """
        Namespace class for CSV column names.
        """
        EMAIL = "email"

    def __init__(self, *args, **kwargs):
        """
        Initializes form: puts current user and enterprise_customer into a
        field for later access.

        Arguments:
            user (django.contrib.auth.models.User): current user
            enterprise_customer (enterprise.models.EnterpriseCustomer): current customer
        """
        user = kwargs.pop('user', None)
        self._user = user
        self._enterprise_customer = kwargs.pop('enterprise_customer', None)
        super(ManageLearnersForm, self).__init__(*args, **kwargs)

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
        bulk_entry = len(split_usernames_and_emails(email)) > 1
        if bulk_entry:
            for email in split_usernames_and_emails(email):
                validate_email_to_link(
                    email,
                    None,
                    ValidationMessages.INVALID_EMAIL_OR_USERNAME,
                    ignore_existing=True
                )
            email = email_or_username
        else:
            validate_email_to_link(
                email,
                email_or_username,
                ValidationMessages.INVALID_EMAIL_OR_USERNAME,
                ignore_existing=True
            )

        return email

    def clean_course(self):
        """
        Verify course ID and retrieve course details.
        """
        course_id = self.cleaned_data[self.Fields.COURSE].strip()
        if not course_id:
            return None
        try:
            client = EnrollmentApiClient()
            return client.get_course_details(course_id)
        except (HttpClientError, HttpServerError):
            raise ValidationError(ValidationMessages.INVALID_COURSE_ID.format(course_id=course_id))

    def clean_program(self):
        """
        Clean program.

        Try obtaining program treating form value as program UUID or title.

        Returns:
            dict: Program information if program found
        """
        program_id = self.cleaned_data[self.Fields.PROGRAM].strip()
        if not program_id:
            return None

        try:
            client = CourseCatalogApiClient(self._user, self._enterprise_customer.site)
            program = client.get_program_by_uuid(program_id) or client.get_program_by_title(program_id)
        except MultipleProgramMatchError as exc:
            raise ValidationError(ValidationMessages.MULTIPLE_PROGRAM_MATCH.format(program_count=exc.programs_matched))
        except (HttpClientError, HttpServerError):
            raise ValidationError(ValidationMessages.INVALID_PROGRAM_ID.format(program_id=program_id))

        if not program:
            raise ValidationError(ValidationMessages.INVALID_PROGRAM_ID.format(program_id=program_id))

        if program['status'] != ProgramStatuses.ACTIVE:
            raise ValidationError(
                ValidationMessages.PROGRAM_IS_INACTIVE.format(program_id=program_id, status=program['status'])
            )

        return program

    def clean_notify(self):
        """
        Clean the notify_on_enrollment field.
        """
        return self.cleaned_data.get(self.Fields.NOTIFY, self.NotificationTypes.DEFAULT)

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
        cleaned_data[self.Fields.NOTIFY] = self.clean_notify()

        self._validate_course()
        self._validate_program()

        if self.data.get(self.Fields.PROGRAM, None) and self.data.get(self.Fields.COURSE, None):
            raise ValidationError(ValidationMessages.COURSE_AND_PROGRAM_ERROR)

        return cleaned_data

    def _validate_course(self):
        """
        Verify that the selected mode is valid for the given course .
        """
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

    def _validate_program(self):
        """
        Verify that selected mode is available for program and all courses in the program
        """
        program = self.cleaned_data.get(self.Fields.PROGRAM)
        if not program:
            return

        course_runs = get_course_runs_from_program(program)
        try:
            client = CourseCatalogApiClient(self._user, self._enterprise_customer.site)
            available_modes = client.get_common_course_modes(course_runs)
            course_mode = self.cleaned_data.get(self.Fields.COURSE_MODE)
        except (HttpClientError, HttpServerError):
            raise ValidationError(
                ValidationMessages.FAILED_TO_OBTAIN_COURSE_MODES.format(program_title=program.get("title"))
            )

        if not course_mode:
            raise ValidationError(ValidationMessages.COURSE_WITHOUT_COURSE_MODE)
        if course_mode not in available_modes:
            raise ValidationError(ValidationMessages.COURSE_MODE_NOT_AVAILABLE.format(
                mode=course_mode, program_title=program.get("title"), modes=", ".join(available_modes)
            ))


class EnterpriseCustomerAdminForm(forms.ModelForm):
    """
    Alternate form for the EnterpriseCustomer admin page.

    This form fetches catalog names and IDs from the course catalog API.
    """
    class Meta:
        model = EnterpriseCustomer
        fields = (
            "name",
            "slug",
            "country",
            "active",
            "customer_type",
            "site",
            "catalog",
            "enable_data_sharing_consent",
            "enforce_data_sharing_consent",
            "enable_audit_enrollment",
            "enable_audit_data_reporting",
            "replace_sensitive_sso_username",
            "hide_course_original_price",
            "enable_portal_code_management_screen",
        )

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
            # pylint: disable=bad-continuation
            help_text='<a id="catalog-details-link" href="#" target="_blank" '
                      'data-url-template="{catalog_admin_change_url}"> View catalog details.</a>'
                      ' <p style="margin-top:-4px;"><a href="{catalog_admin_add_url}"'
                      ' target="_blank">Create a new catalog</a></p>'.format(
                catalog_admin_change_url=utils.get_catalog_admin_url_template(mode='change'),
                catalog_admin_add_url=utils.get_catalog_admin_url_template(mode='add'))
        )

    def get_catalog_options(self):
        """
        Retrieve a list of catalog ID and name pairs.

        Once retrieved, these name pairs can be used directly as a value
        for the `choices` argument to a ChoiceField.
        """
        # TODO: We will remove the discovery service catalog implementation
        # once we have fully migrated customer's to EnterpriseCustomerCatalogs.
        # For now, this code will prevent an admin from creating a new
        # EnterpriseCustomer with a discovery service catalog. They will have to first
        # save the EnterpriseCustomer admin form and then edit the EnterpriseCustomer
        # to add a discovery service catalog.
        if hasattr(self.instance, 'site'):
            catalog_api = CourseCatalogApiClient(self.user, self.instance.site)
        else:
            catalog_api = CourseCatalogApiClient(self.user)
        catalogs = catalog_api.get_all_catalogs()
        # order catalogs by name.
        catalogs = sorted(catalogs, key=lambda catalog: catalog.get('name', '').lower())

        return BLANK_CHOICE_DASH + [
            (catalog['id'], catalog['name'],)
            for catalog in catalogs
        ]

    def clean(self):
        """
        Clean form fields prior to database entry.

        In this case, the major cleaning operation is substituting a None value for a blank
        value in the Catalog field.
        """
        cleaned_data = super(EnterpriseCustomerAdminForm, self).clean()
        if 'catalog' in cleaned_data and not cleaned_data['catalog']:
            cleaned_data['catalog'] = None
        return cleaned_data


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
        help_text = ''
        if saml_provider_configuration:
            provider_id = self.instance.provider_id
            url = reverse('admin:{}_{}_add'.format(
                saml_provider_configuration._meta.app_label,
                saml_provider_configuration._meta.model_name))
            if provider_id:
                identity_provider = utils.get_identity_provider(provider_id)
                if identity_provider:
                    update_url = url + '?source={}'.format(identity_provider.pk)
                    help_text = '<p><a href="{update_url}" target="_blank">View "{identity_provider}" details</a><p>'.\
                        format(update_url=update_url, identity_provider=identity_provider.name)
                else:
                    help_text += '<p style="margin-top:-5px;"> Make sure you have added a valid provider_id.</p>'
            else:
                help_text += '<p style="margin-top:-5px;"><a target="_blank" href={add_url}>' \
                             'Create a new identity provider</a></p>'.format(add_url=url)

        if idp_choices is not None:
            self.fields['provider_id'] = forms.TypedChoiceField(
                choices=idp_choices,
                label=_('Identity Provider'),
                help_text=mark_safe(help_text),
            )

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

        identity_provider = utils.get_identity_provider(provider_id)
        if not identity_provider:
            # This should not happen, as identity providers displayed in drop down are fetched dynamically.
            message = _(
                "The specified Identity Provider does not exist. For more "
                "information, contact a system administrator.",
            )
            # Log message for debugging
            logger.exception(message)

            raise ValidationError(message)

        if identity_provider and identity_provider.site != enterprise_customer.site:
            raise ValidationError(
                _(
                    "The site for the selected identity provider "
                    "({identity_provider_site}) does not match the site for "
                    "this enterprise customer ({enterprise_customer_site}). "
                    "To correct this problem, select a site that has a domain "
                    "of '{identity_provider_site}', or update the identity "
                    "provider to '{enterprise_customer_site}'."
                ).format(
                    enterprise_customer_site=enterprise_customer.site,
                    identity_provider_site=identity_provider.site,
                ),
            )


class EnterpriseCustomerReportingConfigAdminForm(forms.ModelForm):
    """
    Alternate form for the EnterpriseCustomerReportingConfiguration admin page.

    This form uses the PasswordInput widget to obscure passwords as they are
    being entered by the user.
    """
    enterprise_customer_catalogs = forms.ModelMultipleChoiceField(
        EnterpriseCustomerCatalog.objects.all(),
        required=False,
    )

    class Meta:
        model = EnterpriseCustomerReportingConfiguration
        fields = (
            "enterprise_customer",
            "active",
            "data_type",
            "report_type",
            "delivery_method",
            "pgp_encryption_key",
            "frequency",
            "day_of_month",
            "day_of_week",
            "hour_of_day",
            "email",
            "decrypted_password",
            "sftp_hostname",
            "sftp_port",
            "sftp_username",
            "decrypted_sftp_password",
            "sftp_file_path",
            "enterprise_customer_catalogs",
        )
        widgets = {
            'decrypted_password': forms.widgets.PasswordInput(),
            'decrypted_sftp_password': forms.widgets.PasswordInput(),
        }

    def clean(self):
        """
        Override of clean method to perform additional validation
        """
        cleaned_data = super(EnterpriseCustomerReportingConfigAdminForm, self).clean()
        report_customer = cleaned_data.get('enterprise_customer')

        # Check that any selected catalogs are tied to the selected enterprise.
        invalid_catalogs = [
            '{} ({})'.format(catalog.title, catalog.uuid)
            for catalog in cleaned_data.get('enterprise_customer_catalogs')
            if catalog.enterprise_customer != report_customer
        ]

        if invalid_catalogs:
            message = _(
                'These catalogs for reporting do not match enterprise'
                'customer {enterprise_customer}: {invalid_catalogs}',
            ).format(
                enterprise_customer=report_customer,
                invalid_catalogs=invalid_catalogs,
            )
            self.add_error('enterprise_customer_catalogs', message)


class TransmitEnterpriseCoursesForm(forms.Form):
    """
    Form to transmit courses metadata for enterprise customers.
    """
    channel_worker_username = forms.CharField(
        label=_('Enter enterprise channel worker username.'),
        required=True
    )

    def clean_channel_worker_username(self):
        """
        Clean enterprise channel worker user form field

        Returns:
            str: the cleaned value of channel user username for transmitting courses metadata.
        """
        channel_worker_username = self.cleaned_data['channel_worker_username'].strip()

        try:
            User.objects.get(username=channel_worker_username)
        except User.DoesNotExist:
            raise ValidationError(
                ValidationMessages.INVALID_CHANNEL_WORKER.format(
                    channel_worker_username=channel_worker_username
                )
            )

        return channel_worker_username


class SystemWideEnterpriseUserRoleAssignmentForm(UserRoleAssignmentAdminForm):
    """
    Form for SystemWideEnterpriseUserRoleAssignments.
    """

    class Meta:
        model = SystemWideEnterpriseUserRoleAssignment
        fields = ['user', 'role']


class EnterpriseFeatureUserRoleAssignmentForm(UserRoleAssignmentAdminForm):
    """
    Form for EnterpriseFeatureUserRoleAssignments.
    """

    class Meta:
        model = EnterpriseFeatureUserRoleAssignment
        fields = ['user', 'role']
