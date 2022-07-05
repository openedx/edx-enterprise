"""
Forms to be used in the enterprise djangoapp.
"""

import re
from logging import getLogger

from config_models.admin import ConfigurationModelAdmin
from edx_rbac.admin.forms import UserRoleAssignmentAdminForm

from django import forms
from django.conf import settings
from django.contrib import admin, auth
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.db.models.fields import BLANK_CHOICE_DASH
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _

from enterprise import utils
from enterprise.admin.utils import email_or_username__to__email, split_usernames_and_emails
from enterprise.admin.widgets import SubmitInput
from enterprise.models import (
    AdminNotification,
    BulkCatalogQueryUpdateCommandConfiguration,
    EnterpriseCustomer,
    EnterpriseCustomerCatalog,
    EnterpriseCustomerIdentityProvider,
    EnterpriseCustomerReportingConfiguration,
    EnterpriseFeatureUserRoleAssignment,
    SystemWideEnterpriseUserRoleAssignment,
)
from enterprise.utils import ValidationMessages, validate_email_to_link

try:
    from common.djangoapps.third_party_auth.models import SAMLProviderConfig as saml_provider_configuration
except ImportError:
    saml_provider_configuration = None

logger = getLogger(__name__)
User = auth.get_user_model()


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
            "by the heading 'email' in the first row. Optionally, the .csv file may contain "
            "a column of course run keys, indicated by the heading 'course_id' in the first row, to "
            "enroll learners in multiple courses."
        )
    )
    course = forms.CharField(
        label=_("Enroll these learners in this course"), required=False,
        help_text=_("To enroll learners in a course, enter a course ID."),
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
    reason = forms.CharField(label=_("Reason for manual enrollment"), required=False)
    sales_force_id = forms.CharField(label=_("Salesforce Opportunity ID"), required=False)
    discount = forms.DecimalField(
        label=_("Discount percentage for manual enrollment"),
        help_text=_("Discount percentage should be from 0 to 100"),
        required=True,
        decimal_places=5,
        initial=0.0
    )

    class NotificationTypes:
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

    class Modes:
        """
        Namespace class for form modes.
        """
        MODE_SINGULAR = "singular"
        MODE_BULK = "bulk"

    class Fields:
        """
        Namespace class for field names.
        """
        GENERAL_ERRORS = forms.forms.NON_FIELD_ERRORS

        EMAIL_OR_USERNAME = "email_or_username"
        BULK_UPLOAD = "bulk_upload_csv"
        MODE = "mode"
        COURSE = "course"
        COURSE_MODE = "course_mode"
        NOTIFY = "notify_on_enrollment"
        REASON = "reason"
        SALES_FORCE_ID = "sales_force_id"
        DISCOUNT = "discount"

    class CsvColumns:
        """
        Namespace class for CSV column names.
        """
        EMAIL = "email"
        COURSE_ID = "course_id"

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
        super().__init__(*args, **kwargs)

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
                    self._enterprise_customer,
                    None,
                    ValidationMessages.INVALID_EMAIL_OR_USERNAME,
                    raise_exception=False,
                )
            email = email_or_username
        else:
            validate_email_to_link(
                email,
                self._enterprise_customer,
                email_or_username,
                ValidationMessages.INVALID_EMAIL_OR_USERNAME,
                raise_exception=False,
            )

        return email

    def clean_discount(self):
        """
        Verify that discount value should be from 0 to 100.
        """
        discount = self.cleaned_data[self.Fields.DISCOUNT]
        if discount < 0.0 or discount > 100.0:
            raise ValidationError(ValidationMessages.INVALID_DISCOUNT)
        return discount

    def clean_course(self):
        """
        Verify course ID and retrieve course details.
        """
        course_id = self.cleaned_data[self.Fields.COURSE].strip()
        if not course_id:
            return None
        enterprise_customer = utils.get_enterprise_customer(self._enterprise_customer.uuid)
        course_details = utils.validate_course_exists_for_enterprise(enterprise_customer, course_id)
        return course_details

    def clean_reason(self):
        """
        Clean the reason for enrollment field
        """
        return self.cleaned_data.get(self.Fields.REASON).strip()

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
        cleaned_data = super().clean()

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

        self._validate_bulk_upload()
        self._validate_course()
        self._validate_reason()

        return cleaned_data

    def _validate_bulk_upload(self):
        """
        Verify that when a csv file contains a "course_id" column, there is not a singular course ID
        specified. Also verify that a course mode is specified, which is applied to all enrollments.
        """
        bulk_upload_csv = self.cleaned_data.get(self.Fields.BULK_UPLOAD)
        if bulk_upload_csv:
            bulk_csv_contents = bulk_upload_csv.read()
            csv_column_names = bulk_csv_contents.decode('utf-8').split('\n', 1)[0].split(',')
            if self.CsvColumns.COURSE_ID in csv_column_names:
                # course id column exists in csv, so validate conditionally required fields
                if self.cleaned_data.get(self.Fields.COURSE):
                    raise ValidationError(ValidationMessages.BOTH_COURSE_FIELDS_SPECIFIED)
                if not self.cleaned_data.get(self.Fields.COURSE_MODE):
                    raise ValidationError(ValidationMessages.COURSE_WITHOUT_COURSE_MODE)
                if not self.cleaned_data.get(self.Fields.REASON):
                    raise ValidationError(ValidationMessages.MISSING_REASON)

    def _validate_course(self):
        """
        Verify that the selected mode is valid for the given course.
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

    def _validate_reason(self):
        """
        Verify that the reason field is populated if the new learner(s) is being enrolled
        in a course or program.
        """
        course = self.cleaned_data.get(self.Fields.COURSE)
        reason = self.cleaned_data.get(self.Fields.REASON)

        if course and not reason:
            raise ValidationError(ValidationMessages.MISSING_REASON)


class ManageLearnersDataSharingConsentForm(forms.Form):
    """
    Form to request DSC from a learner.
    """
    email_or_username = forms.CharField(
        label=_("Email/Username"),
        help_text=_("Enter an email address or username."),
        required=True
    )
    course = forms.CharField(
        label=_("Course"),
        help_text=_("Enter the course run key."),
        required=True,
    )

    class Fields:
        """
        Namespace class for field names.
        """
        EMAIL_OR_USERNAME = "email_or_username"
        COURSE = "course"

    def __init__(self, *args, **kwargs):
        """
        Initializes form with current enterprise customer.

        Arguments:
            enterprise_customer (enterprise.models.EnterpriseCustomer): current customer
        """
        self._enterprise_customer = kwargs.pop('enterprise_customer', None)
        super().__init__(*args, **kwargs)

    def clean_course(self):
        """
        Verify course ID has an associated course in LMS.
        """
        course_id = self.cleaned_data[self.Fields.COURSE].strip()
        if not course_id:
            return None
        enterprise_customer = utils.get_enterprise_customer(self._enterprise_customer.uuid)
        utils.validate_course_exists_for_enterprise(enterprise_customer, course_id)
        return course_id

    def clean_email_or_username(self):
        """
        Verify email_or_username has associated user in our database.
        """
        email_or_username = self.cleaned_data[self.Fields.EMAIL_OR_USERNAME].strip()
        email = email_or_username__to__email(email_or_username)
        # Check whether user exists in our database.
        if not User.objects.filter(email=email).exists():
            raise ValidationError(ValidationMessages.USER_NOT_EXIST.format(email=email))

        # Check whether user in linked to the enterprise customer.
        if not self.is_user_linked(email):
            raise ValidationError(ValidationMessages.USER_NOT_LINKED)
        return email

    def is_course_in_catalog(self, course_id):
        """
        Check whether course exists in enterprise customer catalog.
        """
        enterprise_customer = utils.get_enterprise_customer(self._enterprise_customer.uuid)
        return enterprise_customer.catalog_contains_course(course_id)

    def is_user_linked(self, email):
        """
        Check whether user is linked to the enterprise customer or not.
        """
        user = User.objects.get(email=email)
        return utils.get_enterprise_customer_user(user.id, self._enterprise_customer.uuid)


class EnterpriseCustomerAdminForm(forms.ModelForm):
    """
    Alternate form for the EnterpriseCustomer admin page.
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
            "enable_data_sharing_consent",
            "enforce_data_sharing_consent",
            "enable_audit_enrollment",
            "enable_audit_data_reporting",
            "replace_sensitive_sso_username",
            "hide_course_original_price",
            "enable_portal_code_management_screen",
            "enable_portal_subscription_management_screen",
            "enable_learner_portal",
            "enable_learner_portal_offers",
            "enable_portal_learner_credit_management_screen",
            "hide_labor_market_data",
            "enable_integrated_customer_learner_portal_search",
            "enable_analytics_screen",
            "enable_portal_reporting_config_screen",
            "enable_portal_saml_configuration_screen",
            "enable_portal_lms_configurations_screen",
            "enable_universal_link",
            "enable_browse_and_request",
            "enable_slug_login",
            "contact_email",
            "default_contract_discount",
            "default_language",
            "sender_alias",
            "reply_to",
        )


class EnterpriseCustomerCatalogAdminForm(forms.ModelForm):
    """
        form for EnterpriseCustomerCatalogAdmin class.
    """
    class Meta:
        model = EnterpriseCustomerCatalog
        fields = "__all__"

    preview_button = forms.Field(required=False, label='Actions', widget=SubmitInput(attrs={'value': _('Preview')}),
                                 help_text=_("Hold Ctrl when clicking on button to open Preview in new tab"))

    @staticmethod
    def get_catalog_preview_uuid(post_data):
        """
        Return the uuid of the catalog the preview button was clicked on
        There must be only one preview button in the POST data.

        e.g: 'enterprise_customer_catalogs-0-preview_button'
        """
        preview_button_expression = re.compile(r'enterprise_customer_catalogs-\d+-preview_button')
        clicked_button_index_expression = re.compile(r'-(.+?)-')
        count = 0
        preview_button_index = None
        for key, _ in post_data.items():
            if preview_button_expression.match(key):
                count += 1
                preview_button_index = clicked_button_index_expression.search(key).group(1)
        if count == 1:
            return post_data.get('enterprise_customer_catalogs-' + preview_button_index + '-uuid')
        return None


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
        super().__init__(*args, **kwargs)
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
        super().clean()

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

        # There should be always one default provider in case an enterprise has multiple providers.
        identity_provider_total_forms = int(self.data.get('enterprise_customer_identity_providers-TOTAL_FORMS'))
        default_provider_values = []
        for form_num in range(identity_provider_total_forms):
            default_provider_values.append(
                self.data.get('enterprise_customer_identity_providers-{}-default_provider'.format(form_num))
            )
        providers_marked_default = default_provider_values.count('on')
        if providers_marked_default > 1:
            raise ValidationError('Please select only one default provider.')
        if identity_provider_total_forms > 1 and providers_marked_default == 0:
            raise ValidationError('Please select one default provider.')


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
            "enable_compression",
            "pgp_encryption_key",
            "frequency",
            "day_of_month",
            "day_of_week",
            "hour_of_day",
            "include_date",
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
        cleaned_data = super().clean()
        report_customer = cleaned_data.get('enterprise_customer')
        data_type = cleaned_data.get('data_type')

        if data_type in EnterpriseCustomerReportingConfiguration.PEARSON_ONLY_REPORTS \
                and report_customer.name != 'Pearson':
            message = _(
                'This data_type "{data_type}" is not supported for enterprise'
                'customer {enterprise_customer}. Please select a different data_type.',
            ).format(
                enterprise_customer=report_customer,
                data_type=data_type,
            )
            self.add_error('data_type', message)

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
        except User.DoesNotExist as error:
            raise ValidationError(
                ValidationMessages.INVALID_CHANNEL_WORKER.format(
                    channel_worker_username=channel_worker_username
                )
            ) from error

        return channel_worker_username


class SystemWideEnterpriseUserRoleAssignmentForm(UserRoleAssignmentAdminForm):
    """
    Form for SystemWideEnterpriseUserRoleAssignments.
    """

    class Meta:
        model = SystemWideEnterpriseUserRoleAssignment
        fields = [
            'user',
            'role',
            'enterprise_customer',
            'applies_to_all_contexts',
        ]

    def __init__(self, *args, **kwargs):
        """
        Modifies the enterprise_customer queryset to only include
        EnterpriseCustomer instances to which the user for this instance
        of a SystemWideEnterpriseUserRoleAssignment is linked.
        """
        super().__init__(*args, **kwargs)
        try:
            self.fields['enterprise_customer'].queryset = EnterpriseCustomer.objects.filter(
                enterprise_customer_users__user_id=self.instance.user.id,
            )
        except SystemWideEnterpriseUserRoleAssignment.user.RelatedObjectDoesNotExist:
            self.fields['enterprise_customer'].queryset = EnterpriseCustomer.objects.none()


class EnterpriseFeatureUserRoleAssignmentForm(UserRoleAssignmentAdminForm):
    """
    Form for EnterpriseFeatureUserRoleAssignments.
    """

    class Meta:
        model = EnterpriseFeatureUserRoleAssignment
        fields = ['user', 'role']


class AdminNotificationForm(forms.ModelForm):
    """
    Alternate form for AdminNotification.
    """

    class Meta:
        model = AdminNotification
        fields = '__all__'
        widgets = {
            'text': forms.Textarea(attrs={'cols': 80, 'rows': 5}),
        }

    def clean(self):
        """
        1. `start_date` and `expiration_date` are mandatory.
        2. `start_date` must always come before the `expiration_date`.
        3.  There must be only one admin notification in a date range.
        """
        cleaned_data = super().clean()

        start_date = cleaned_data.get('start_date', None)
        expiration_date = cleaned_data.get('expiration_date', None)

        if start_date is None or expiration_date is None:
            # Start and expiration dates are mandatory.
            raise ValidationError('Start and expiration dates are mandatory.')

        if expiration_date < start_date:
            # `start_date` must always come before the `expiration_date`
            raise ValidationError({'expiration_date': ['Expiration date should be after start date.']})
        admin_notification = AdminNotification.objects.filter(
            Q(start_date__range=(start_date, expiration_date)) |
            Q(expiration_date__range=(start_date, expiration_date)) |
            Q(start_date__lt=start_date, expiration_date__gt=expiration_date)
        ).exclude(
            pk=self.instance.id
        ).exists()

        if admin_notification:
            # This should not happen, as there can be only one admin notification instance in a particular date range.
            message = _(
                'Please select different date range. There is another notification scheduled in this date range.',
            )
            logger.exception(message)

            raise ValidationError(message)
        return cleaned_data


@admin.register(BulkCatalogQueryUpdateCommandConfiguration)
class BulkCatalogQueryUpdateCommandConfigurationAdmin(ConfigurationModelAdmin):
    """
    Admin form for the BulkCatalogQueryUpdateCommandConfiguration model
    """
