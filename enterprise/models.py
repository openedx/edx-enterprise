
# -*- coding: utf-8 -*-
"""
Database models for enterprise.
"""

import collections
import json
import os
from decimal import Decimal
from logging import getLogger
from uuid import uuid4

import six
from django_countries.fields import CountryField
from edx_rbac.models import UserRole, UserRoleAssignment
from edx_rest_api_client.exceptions import HttpClientError
from fernet_fields import EncryptedCharField
from jsonfield.encoder import JSONEncoder
from jsonfield.fields import JSONField
from multi_email_field.fields import MultiEmailField
from simple_history.models import HistoricalRecords
from six.moves.urllib.parse import urljoin  # pylint: disable=import-error,ungrouped-imports

from django.apps import apps
from django.conf import settings
from django.contrib import auth
from django.contrib.sites.models import Site
from django.core import mail
from django.core.exceptions import NON_FIELD_ERRORS, ObjectDoesNotExist, ValidationError
from django.core.files.storage import default_storage
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import IntegrityError, models, transaction
from django.template import Context, Template
from django.urls import reverse
from django.utils.encoding import force_bytes, force_text, python_2_unicode_compatible
from django.utils.functional import cached_property, lazy
from django.utils.http import urlencode, urlquote
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext
from django.utils.translation import ugettext_lazy as _

from model_utils.models import TimeStampedModel

from enterprise import utils
from enterprise.api_client.discovery import CourseCatalogApiClient, get_course_catalog_api_service_client
from enterprise.api_client.ecommerce import EcommerceApiClient
from enterprise.api_client.enterprise_catalog import EnterpriseCatalogApiClient
from enterprise.api_client.lms import EnrollmentApiClient, ThirdPartyAuthApiClient, parse_lms_api_datetime
from enterprise.constants import (
    ALL_ACCESS_CONTEXT,
    AVAILABLE_LANGUAGES,
    ENTERPRISE_ADMIN_ROLE,
    ENTERPRISE_OPERATOR_ROLE,
    DefaultColors,
    json_serialized_course_modes,
)
from enterprise.utils import (
    CourseEnrollmentDowngradeError,
    CourseEnrollmentPermissionError,
    NotConnectedToOpenEdX,
    create_tableau_user,
    delete_tableau_user,
    get_configuration_value,
    get_ecommerce_worker_user,
    get_enterprise_worker_user,
    get_platform_logo_url,
    track_enrollment,
)
from enterprise.validators import (
    validate_content_filter_fields,
    validate_hex_color,
    validate_image_extension,
    validate_image_size,
)

try:
    from common.djangoapps.student.models import CourseEnrollment
    from lms.djangoapps.email_marketing.tasks import update_user
except ImportError:
    update_user = None
    CourseEnrollment = None

LOGGER = getLogger(__name__)
User = auth.get_user_model()  # pylint: disable=invalid-name
mark_safe_lazy = lazy(mark_safe, six.text_type)  # pylint: disable=invalid-name


class EnterpriseCustomerManager(models.Manager):
    """
    Model manager for :class:`.EnterpriseCustomer` model.

    Filters out inactive Enterprise Customers, otherwise works the same as default model manager.
    """

    # This manager filters out some records, hence according to the Django docs it must not be used
    # for related field access. Although False is default value, it still makes sense to set it explicitly
    # https://docs.djangoproject.com/en/1.10/topics/db/managers/#base-managers
    use_for_related_fields = False

    def get_queryset(self):
        """
        Return a new QuerySet object. Filters out inactive Enterprise Customers.
        """
        return super().get_queryset().filter(active=True)


@python_2_unicode_compatible
class EnterpriseCustomerType(TimeStampedModel):
    """
    Enterprise Customer Types are used to differentiate Enterprise learners.

    .. no_pii:
    """

    class Meta:
        app_label = 'enterprise'
        verbose_name = _('Enterprise Customer Type')
        verbose_name_plural = _('Enterprise Customer Types')
        ordering = ['name']

    name = models.CharField(
        max_length=25,
        blank=False,
        help_text=_(
            'Specifies enterprise customer type.'
        )
    )

    def __str__(self):
        """
        Return human-readable string representation.
        """
        return self.name

    def __repr__(self):
        """
        Return uniquely identifying string representation.
        """
        return self.__str__()


def get_default_customer_type():
    """
    Get default enterprise customer type id to use when creating a new EnterpriseCustomer model.
    """
    enterprise_customer_type, __ = EnterpriseCustomerType.objects.get_or_create(
        name='Enterprise'
    )
    return enterprise_customer_type.id


@python_2_unicode_compatible
class EnterpriseCustomer(TimeStampedModel):
    """
    Enterprise Customer is an organization or a group of people that "consumes" courses.

    Users associated with an Enterprise Customer take courses on the edX platform.

    Enterprise Customer might be providing certain benefits to their members, like discounts to paid course
    enrollments, and also might request (or require) sharing learner results with them.

    Fields:
        uuid (UUIDField, PRIMARY KEY): Enterprise Customer code - used to reference this Enterprise Customer in
            other parts of the system (SSO, ecommerce, analytics etc.).
        name (:class:`django.db.models.CharField`): Enterprise Customer name.
        active (:class:`django.db.models.BooleanField`): used to mark inactive Enterprise Customers - implements
            "soft delete" pattern.

    .. no_pii:
    """

    class Meta:
        app_label = 'enterprise'
        verbose_name = _("Enterprise Customer")
        verbose_name_plural = _("Enterprise Customers")
        ordering = ['created']

    objects = models.Manager()
    active_customers = EnterpriseCustomerManager()

    uuid = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    name = models.CharField(max_length=255, blank=False, null=False, help_text=_("Enterprise Customer name."))
    slug = models.SlugField(
        max_length=30, unique=True, default='default',
        help_text=(
            'A short string uniquely identifying this enterprise. '
            'Cannot contain spaces and should be a usable as a CSS class. Examples: "ubc", "mit-staging"'
        )
    )
    active = models.BooleanField(default=True)
    country = CountryField(null=True)
    hide_course_original_price = models.BooleanField(
        default=False,
        help_text=_(
            "Specify whether display the course original price on enterprise course landing page or not."
        )
    )
    history = HistoricalRecords()
    site = models.ForeignKey(
        Site,
        related_name="enterprise_customers",
        on_delete=models.deletion.CASCADE
    )

    AT_ENROLLMENT = 'at_enrollment'
    EXTERNALLY_MANAGED = 'externally_managed'
    DATA_SHARING_CONSENT_CHOICES = (
        (AT_ENROLLMENT, 'At Enrollment'),
        (EXTERNALLY_MANAGED, 'Managed externally')
    )

    enable_data_sharing_consent = models.BooleanField(
        default=False,
        help_text=_(
            "Specifies whether data sharing consent is enabled or disabled "
            "for learners signing in through this enterprise customer. If "
            "disabled, consent will not be requested, and eligible data will "
            "not be shared."
        )
    )

    enforce_data_sharing_consent = models.CharField(
        max_length=25,
        blank=False,
        choices=DATA_SHARING_CONSENT_CHOICES,
        default=AT_ENROLLMENT,
        help_text=_(
            "Specifies whether data sharing consent is optional, is required "
            "at login, or is required at enrollment."
        )
    )

    enable_audit_enrollment = models.BooleanField(
        default=False,
        help_text=_(
            "Specifies whether the audit track enrollment option will be displayed in the course enrollment view."
        )
    )

    enable_audit_data_reporting = models.BooleanField(
        default=False,
        help_text=_(
            "Specifies whether to pass-back audit track enrollment data through an integrated channel."
        )
    )

    replace_sensitive_sso_username = models.BooleanField(
        default=False,
        help_text=_(
            "Specifies whether to replace the display of potentially sensitive SSO usernames "
            "with a more generic name, e.g. EnterpriseLearner."
        )
    )

    # This setting is a temporary fix to hide the cohort API.
    # It should be removed/refactored once there's a better model for organization-wide settings
    # in edx-platform.
    enable_autocohorting = models.BooleanField(
        default=False,
        help_text=_(
            "Specifies whether the customer is able to assign learners to cohorts upon enrollment."
        )
    )
    customer_type = models.ForeignKey(
        EnterpriseCustomerType,
        verbose_name=_('Customer Type'),
        default=get_default_customer_type,
        help_text=_(
            'Specifies enterprise customer type.'
        ), on_delete=models.CASCADE
    )

    enable_portal_code_management_screen = models.BooleanField(  # pylint: disable=invalid-name
        default=False,
        help_text=_("Specifies whether to allow access to the code management screen in the admin portal.")
    )

    enable_portal_reporting_config_screen = models.BooleanField(  # pylint: disable=invalid-name
        default=False,
        help_text=_("Specifies whether to allow access to the reporting configurations screen in the admin portal.")
    )

    enable_portal_subscription_management_screen = models.BooleanField(  # pylint: disable=invalid-name
        default=False,
        help_text=_("Specifies whether to allow access to the subscription management screen in the admin portal.")
    )

    enable_portal_saml_configuration_screen = models.BooleanField(  # pylint: disable=invalid-name
        default=False,
        help_text=_("Specifies whether to allow access to the saml configuration screen in the admin portal")
    )

    enable_learner_portal = models.BooleanField(
        default=False,
        help_text=_("Specifies whether the enterprise learner portal site should be made known to the learner.")
    )

    enable_integrated_customer_learner_portal_search = models.BooleanField(  # pylint: disable=invalid-name
        default=True,
        help_text=_(
            "Specifies whether a learner for an integrated channel customer can navigate the enterprise learner "
            "portal site using the main menu."
        )
    )

    enable_analytics_screen = models.BooleanField(  # pylint: disable=invalid-name
        default=False,
        help_text=_("Specifies whether to allow access to the analytics screen in the admin portal.")
    )

    enable_portal_lms_configurations_screen = models.BooleanField(  # pylint: disable=invalid-name
        default=False,
        help_text=_("Specifies whether to allow access to the external LMS configuration screen in the admin portal.")
    )

    enable_slug_login = models.BooleanField(
        default=False,
        help_text=_("Specifies whether the learner should be able to login through enterprise's slug login")
    )

    contact_email = models.EmailField(
        null=True,
        blank=True,
        help_text=_("Email to be displayed as public point of contact for enterprise.")
    )

    default_contract_discount = models.DecimalField(
        null=True,
        blank=True,
        max_digits=8,
        decimal_places=5,
        help_text=_(
            "Specifies the discount percent used for enrollments from the enrollment API "
            "where capturing the discount per order is not possible. "
            "This is passed to ecommerce when creating orders for financial data reporting."
        )
    )
    default_language = models.CharField(
        max_length=25,
        null=True,
        blank=True,
        choices=AVAILABLE_LANGUAGES,
        default=None,
        help_text=_(
            "Specifies the default language for all the learners of this enterprise customer."
        )
    )

    sender_alias = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text=_(
            "Specifies the sender alias which will be used in enterprise customer Assign/Remind/Revoke emails."
        )
    )

    @property
    def enterprise_customer_identity_provider(self):  # pylint: disable=invalid-name
        """
        Returns the first instance from EnterpriseCustomerIdentityProvider relation.
        """
        # pylint: disable=no-member
        return self.enterprise_customer_identity_providers.first()

    @property
    def identity_provider(self):
        """
        Return the first identity provider id associated with this enterprise customer.
        """
        # pylint: disable=no-member
        identity_provider = self.enterprise_customer_identity_providers.first()
        if identity_provider:
            return identity_provider.provider_id
        LOGGER.info("No linked identity provider found for enterprise customer: %s", self.uuid)
        return None

    @property
    def identity_providers(self):
        """
        Return the identity providers associated with this enterprise customer.
        """
        return self.enterprise_customer_identity_providers.all()

    @property
    def identity_provider_ids(self):
        """
        Return the identity provider Ids associated with this enterprise customer.
        """
        return list(self.identity_providers.values_list('provider_id', flat=True))

    @property
    def has_identity_providers(self):
        """
        Return True if there are any identity providers associated with this enterprise customer.
        """
        # pylint: disable=no-member
        return self.enterprise_customer_identity_providers.exists()

    @property
    def has_multiple_idps(self):
        """
        Return True if there are any identity providers associated with this enterprise customer.
        """
        # pylint: disable=no-member
        return self.enterprise_customer_identity_providers.count() > 1

    @property
    def has_single_idp(self):
        """
        Return True if there are exactly one identity provider associated with this enterprise customer.
        """
        # pylint: disable=no-member
        return self.enterprise_customer_identity_providers.count() == 1

    @property
    def sync_learner_profile_data(self):
        """
        Return the sync_learner_profile data flag for the identity provider associated with this enterprise customer.

        Returns False if enterprise customer does not have any identity provider.
        """
        # pylint: disable=no-member
        return all(
            identity_provider.sync_learner_profile_data
            for identity_provider in self.identity_providers
        ) if self.has_identity_providers else False

    def get_tpa_hint(self, tpa_hint_param=None):
        """
        :param tpa_hint_param: query param passed in the URL.
        :return: tpa_hint to redirect
        """

        # if tpa_hint_param is provided and it is a linked identity provider, use it as tpa_hint
        if tpa_hint_param and tpa_hint_param in self.identity_provider_ids:
            return tpa_hint_param
        # if there is only one identity provider linked with the customer and tpa_hint_param was not provider.
        if self.has_single_idp and not tpa_hint_param:
            return self.identity_providers.first().provider_id
        # Now if there is not any linked identity provider OR there are multiple identity providers.
        return None

    def __str__(self):
        """
        Return human-readable string representation.
        """
        # pylint: disable=no-member
        return "<EnterpriseCustomer {code:x}: {name}>".format(code=self.uuid.time_low, name=self.name)

    def __repr__(self):
        """
        Return uniquely identifying string representation.
        """
        return self.__str__()

    def enforces_data_sharing_consent(self, enforcement_location):
        """
        Determine whether the enterprise customer enforce data sharing consent at the given point.

        Args:
            enforcement_location (str): the point where to see data sharing consent state.
            argument can either be 'at_enrollment' or 'externally_managed'
        """
        return self.requests_data_sharing_consent and self.enforce_data_sharing_consent == enforcement_location

    @property
    def requests_data_sharing_consent(self):
        """
        Determine whether the enterprise customer has enabled the data sharing consent request.
        """
        return self.enable_data_sharing_consent and self.enforce_data_sharing_consent != self.EXTERNALLY_MANAGED

    @property
    def enables_audit_data_reporting(self):
        """
        Determine whether the enterprise customer has enabled the ability to report/pass-back audit track data.
        """
        return self.enable_audit_enrollment and self.enable_audit_data_reporting

    @property
    def serialized(self):
        """Return a serialized version of this customer."""
        from enterprise.api.v1 import serializers  # pylint: disable=import-outside-toplevel
        return serializers.EnterpriseCustomerSerializer(self).data

    @property
    def safe_branding_configuration(self):
        """
        Return the associated EnterpriseCustomerBrandingConfiguration object OR default branding config

        This function should always be used to access the customer's branding_configuration and prevent
        uncaught RelatedObjectDoesNotExist exceptions when accessed directly.
        """
        try:
            branding_config = self.branding_configuration  # pylint: disable=no-member
        except EnterpriseCustomerBrandingConfiguration.DoesNotExist:
            branding_config = self._get_default_branding_configuration()
        return branding_config

    def _get_default_branding_configuration(self):
        """
        Return the default EnterpriseCustomerBrandingConfiguration object
        """
        return EnterpriseCustomerBrandingConfiguration(
            enterprise_customer=self,
            primary_color=DefaultColors.PRIMARY,
            secondary_color=DefaultColors.SECONDARY,
            tertiary_color=DefaultColors.TERTIARY,
        )

    def get_data_sharing_consent_text_overrides(self, published_only=True):
        """
        Return DataSharingConsentTextOverrides associated with this instance.
        """
        # pylint: disable=invalid-name
        DataSharingConsentTextOverrides = apps.get_model('consent', 'DataSharingConsentTextOverrides')
        queryset = DataSharingConsentTextOverrides.objects.filter(enterprise_customer=self)
        if published_only:
            queryset = queryset.filter(published=True)
        return queryset.first()

    def get_course_enrollment_url(self, course_key):
        """
        Return enterprise landing page url for the given course.

        Arguments:
            course_key (str): The course key for the course to be displayed.
        Returns:
            (str): Enterprise landing page url.
        """
        url = urljoin(
            get_configuration_value('LMS_ROOT_URL', settings.LMS_ROOT_URL),
            reverse(
                'enterprise_course_enrollment_page',
                kwargs={'enterprise_uuid': self.uuid, 'course_key': course_key}
            )
        )
        return utils.update_query_parameters(url, utils.get_enterprise_utm_context(self))

    def get_course_run_enrollment_url(self, course_run_key):
        """
        Return enterprise landing page url for the given course.

        Arguments:
            course_run_key (str): The course run id for the course to be displayed.
        Returns:
            (str): Enterprise landing page url.
        """
        url = urljoin(
            get_configuration_value('LMS_ROOT_URL', settings.LMS_ROOT_URL),
            reverse(
                'enterprise_course_run_enrollment_page',
                kwargs={'enterprise_uuid': self.uuid, 'course_id': course_run_key}
            )
        )
        return utils.update_query_parameters(url, utils.get_enterprise_utm_context(self))

    def get_program_enrollment_url(self, program_uuid):
        """
        Return enterprise landing page url for the given program.

        Arguments:
            program_uuid (str): The program UUID.
        Returns:
            (str): Enterprise program landing page url.
        """
        url = urljoin(
            get_configuration_value('LMS_ROOT_URL', settings.LMS_ROOT_URL),
            reverse(
                'enterprise_program_enrollment_page',
                kwargs={'enterprise_uuid': self.uuid, 'program_uuid': program_uuid}
            )
        )
        return utils.update_query_parameters(url, utils.get_enterprise_utm_context(self))

    def catalog_contains_course(self, course_run_id):
        """
        Determine if the specified course run is contained in enterprise customer catalogs.

        Arguments:
            course_run_id (str): The string ID of the course or course run in question

        Returns:
            bool: Whether the enterprise catalog includes the given course run.
        """
        if EnterpriseCatalogApiClient().enterprise_contains_content_items(self.uuid, [course_run_id]):
            return True

        return False

    def enroll_user_pending_registration(self, email, course_mode, *course_ids, **kwargs):
        """
        Create pending enrollments for the user in any number of courses, which will take effect on registration.

        Args:
            email: The email address for the pending link to be created
            course_mode: The mode with which the eventual enrollment should be created
            *course_ids: An iterable containing any number of course IDs to eventually enroll the user in.
            cohort (optional): name of cohort to assign
        Returns:
            The PendingEnterpriseCustomerUser attached to the email address
        """
        pending_ecu, __ = PendingEnterpriseCustomerUser.objects.get_or_create(
            enterprise_customer=self,
            user_email=email
        )
        for course_id in course_ids:
            PendingEnrollment.objects.update_or_create(
                user=pending_ecu,
                course_id=course_id,
                defaults={
                    'course_mode': course_mode,
                    'cohort_name': kwargs.get('cohort', None),
                    'source': kwargs.get('enrollment_source', None),
                    'discount_percentage': Decimal(kwargs.get('discount', 0.0)).quantize(Decimal('0.00001')),
                    'sales_force_id': kwargs.get('sales_force_id', None),
                }
            )
        return pending_ecu

    def clear_pending_registration(self, email, *course_ids):
        """
        Clear pending enrollments for the user in the given courses.

        Args:
            email: The email address which may have previously been used.
            course_ids: An iterable containing any number of course IDs.
        """
        try:
            pending_ecu = PendingEnterpriseCustomerUser.objects.get(user_email=email, enterprise_customer=self)
        except PendingEnterpriseCustomerUser.DoesNotExist:
            pass
        else:
            PendingEnrollment.objects.filter(user=pending_ecu, course_id__in=course_ids).delete()

    def notify_enrolled_learners(self, catalog_api_user, course_id, users):
        """
        Notify learners about a course in which they've been enrolled.

        Args:
            catalog_api_user: The user for calling the Catalog API
            course_id: The specific course the learners were enrolled in
            users: An iterable of the users or pending users who were enrolled
        """
        course_details = CourseCatalogApiClient(catalog_api_user, self.site).get_course_run(course_id)
        if not course_details:
            LOGGER.warning(
                ugettext("Course details were not found for course key {} - Course Catalog API returned nothing. "
                         "Proceeding with enrollment, but notifications won't be sent").format(course_id)
            )
            return

        course_path = '/courses/{course_id}/course'.format(course_id=course_id)
        params = {}
        # add tap_hint if there is only one IdP attached with enterprise_customer
        if self.identity_providers.count() == 1:
            params = {'tpa_hint': self.identity_providers.first().provider_id}
        course_path = urlquote("{}?{}".format(course_path, urlencode(params)))

        lms_root_url = utils.get_configuration_value_for_site(
            self.site,
            'LMS_ROOT_URL',
            settings.LMS_ROOT_URL
        )
        destination_url = '{site}/{login_or_register}?next={course_path}'.format(
            site=lms_root_url,
            login_or_register='{login_or_register}',  # We don't know the value at this time
            course_path=course_path
        )
        course_name = course_details.get('title')

        try:
            course_start = parse_lms_api_datetime(course_details.get('start'))
        except (TypeError, ValueError):
            course_start = None
            LOGGER.exception(
                'None or empty value passed as course start date.\nCourse Details:\n{course_details}'.format(
                    course_details=course_details,
                )
            )

        with mail.get_connection() as email_conn:
            for user in users:
                login_or_register = 'register' if isinstance(user, PendingEnterpriseCustomerUser) else 'login'
                destination_url = destination_url.format(login_or_register=login_or_register)
                utils.send_email_notification_message(
                    user=user,
                    enrolled_in={
                        'name': course_name,
                        'url': destination_url,
                        'type': 'course',
                        'start': course_start,
                    },
                    enterprise_customer=self,
                    email_connection=email_conn
                )


class EnterpriseCustomerUserManager(models.Manager):
    """
    Model manager for :class:`.EnterpriseCustomerUser` entity.

    This class should contain methods that create, modify or query :class:`.EnterpriseCustomerUser` entities.
    """

    def __init__(self, *args, **kwargs):
        """
        Initialize custom manager.

        kwargs:
            linked_only (Bool): create a manager with linked learners only if True else all(linked and unlinked) records
        """
        self.linked_only = kwargs.pop('linked_only', True)
        super().__init__(*args, **kwargs)

    def get_queryset(self):
        """
        Return linked or unlinked learners based on how the manager is created.
        """
        if self.linked_only:
            return super().get_queryset().filter(linked=True)

        return super().get_queryset()

    def get(self, **kwargs):
        """
        Overridden get method to return the first element in case of learner with multiple enterprises.

        Raises EnterpriseCustomerUser.DoesNotExist if no records are found.
        """
        fetched_object = self.get_queryset().filter(**kwargs).first()
        if fetched_object:
            return fetched_object
        raise EnterpriseCustomerUser.DoesNotExist

    def get_link_by_email(self, user_email):
        """
        Return link by email.
        """
        try:
            user = User.objects.get(email=user_email)
            try:
                return self.get(user_id=user.id)
            except EnterpriseCustomerUser.DoesNotExist:
                pass
        except User.DoesNotExist:
            pass

        try:
            # return the first element in case of admin/learner with multiple pending enterprise associations.
            return PendingEnterpriseCustomerUser.objects.filter(user_email=user_email).first()
        except PendingEnterpriseCustomerUser.DoesNotExist:
            pass

        return None

    def link_user(self, enterprise_customer, user_email):
        """
        Link user email to Enterprise Customer.

        If :class:`django.contrib.auth.models.User` instance with specified email does not exist,
        :class:`.PendingEnterpriseCustomerUser` instance is created instead.
        """
        try:
            existing_user = User.objects.get(email=user_email)
            self.get_or_create(enterprise_customer=enterprise_customer, user_id=existing_user.id)
        except User.DoesNotExist:
            PendingEnterpriseCustomerUser.objects.get_or_create(enterprise_customer=enterprise_customer,
                                                                user_email=user_email)

    def unlink_user(self, enterprise_customer, user_email):
        """
        Unlink user email from Enterprise Customer.

        If :class:`django.contrib.auth.models.User` instance with specified email does not exist,
        :class:`.PendingEnterpriseCustomerUser` instance is deleted instead.

        Raises EnterpriseCustomerUser.DoesNotExist if instance of :class:`django.contrib.auth.models.User` with
        specified email exists and corresponding :class:`.EnterpriseCustomerUser` instance does not.

        Raises PendingEnterpriseCustomerUser.DoesNotExist exception if instance of
        :class:`django.contrib.auth.models.User` with specified email exists and corresponding
        :class:`.PendingEnterpriseCustomerUser` instance does not.
        """
        try:
            existing_user = User.objects.get(email=user_email)
            # not capturing DoesNotExist intentionally to signal to view that link does not exist
            link_record = self.get(enterprise_customer=enterprise_customer, user_id=existing_user.id)
            link_record.linked = False
            link_record.save()

            if update_user:
                # Remove the SailThru flags for enterprise learner.
                update_user.delay(
                    sailthru_vars={
                        'is_enterprise_learner': False,
                        'enterprise_name': None,
                    },
                    email=user_email
                )

        except User.DoesNotExist:
            # not capturing DoesNotExist intentionally to signal to view that link does not exist
            pending_link = PendingEnterpriseCustomerUser.objects.get(
                enterprise_customer=enterprise_customer, user_email=user_email
            )
            pending_link.delete()

        LOGGER.info(
            'Enterprise learner {%s} successfully unlinked from Enterprise Customer {%s}',
            user_email,
            enterprise_customer.name
        )


@python_2_unicode_compatible
class EnterpriseCustomerUser(TimeStampedModel):
    """
    Model that keeps track of user - enterprise customer affinity.

    Fields:
        enterprise_customer (ForeignKey[:class:`.EnterpriseCustomer`]): enterprise customer
        user_id (:class:`django.db.models.IntegerField`): user identifier

    .. no_pii:
    """

    enterprise_customer = models.ForeignKey(
        EnterpriseCustomer,
        blank=False,
        null=False,
        related_name='enterprise_customer_users',
        on_delete=models.deletion.CASCADE
    )
    user_id = models.PositiveIntegerField(null=False, blank=False, db_index=True)
    active = models.BooleanField(default=True)
    linked = models.BooleanField(default=True)

    objects = EnterpriseCustomerUserManager()
    all_objects = EnterpriseCustomerUserManager(linked_only=False)

    class Meta:
        app_label = 'enterprise'
        verbose_name = _("Enterprise Customer Learner")
        verbose_name_plural = _("Enterprise Customer Learners")
        unique_together = (("enterprise_customer", "user_id"),)
        ordering = ['-active', '-modified']

    def save(self, *args, **kwargs):  # pylint: disable=arguments-differ
        """
        Override to handle creation of EnterpriseCustomerUser records.

        This is needed because of soft deletion of EnterpriseCustomerUser records.
        This will handle all of get_or_create/update_or_create/create methods.
        """
        if self.pk is None:
            # We are trying to create a new object but it may be possible that an existing unlinked
            # record exists, so if an existing record exists then just update that with linked=True
            try:
                existing = EnterpriseCustomerUser.all_objects.get(
                    enterprise_customer=self.enterprise_customer,
                    user_id=self.user_id,
                    linked=False
                )
                self.linked = True
                # An existing record has been found so update auto primary key with primay key of existing record
                self.pk = existing.pk  # pylint: disable=invalid-name
                # Update the kwargs so that Django will update the existing record instead of creating a new one
                kwargs = dict(kwargs, **{'force_insert': False, 'force_update': True})
            except EnterpriseCustomerUser.DoesNotExist:
                # No existing record found so do nothing and proceed with normal operation
                pass

        return super().save(*args, **kwargs)

    @property
    def user(self):
        """
        Return User associated with this instance.

        Return :class:`django.contrib.auth.models.User` instance associated with this
        :class:`EnterpriseCustomerUser` instance via email.
        """
        try:
            return User.objects.get(pk=self.user_id)
        except User.DoesNotExist:
            return None

    @property
    def user_email(self):
        """
        Return linked user email.
        """
        if self.user is not None:
            return self.user.email
        return None

    @property
    def username(self):
        """
        Return linked user's username.
        """
        if self.user is not None:
            return self.user.username
        return None

    @property
    def data_sharing_consent_records(self):
        """
        Return the DataSharingConsent records associated with this EnterpriseCustomerUser.

        Returns:
            QuerySet (DataSharingConsent): The filtered DataSharingConsent QuerySet.
        """
        DataSharingConsent = apps.get_model('consent', 'DataSharingConsent')  # pylint: disable=invalid-name
        return DataSharingConsent.objects.filter(
            enterprise_customer=self.enterprise_customer,
            username=self.username
        )

    def __str__(self):
        """
        Return human-readable string representation.
        """
        return "<EnterpriseCustomerUser {ID}>: {enterprise_name} - {user_id}".format(
            ID=self.id,
            enterprise_name=self.enterprise_customer.name,
            user_id=self.user_id,
        )

    def __repr__(self):
        """
        Return uniquely identifying string representation.
        """
        return self.__str__()

    def get_remote_id(self):
        """
        Retrieve the SSO provider's identifier for this user from the LMS Third Party API.

        Returns None if:
        * the user doesn't exist, or
        * the associated EnterpriseCustomer has no identity_provider, or
        * the remote identity is not found.
        """
        user = self.user
        identity_provider = self.enterprise_customer.identity_provider
        if user and identity_provider:
            enterprise_worker = get_enterprise_worker_user()
            client = ThirdPartyAuthApiClient(enterprise_worker)
            return client.get_remote_id(self.enterprise_customer.identity_provider, user.username)
        return None

    def enroll(self, course_run_id, mode, cohort=None, source_slug=None, discount_percentage=0.0, sales_force_id=None):
        """
        Enroll a user into a course track, and register an enterprise course enrollment.
        """
        enrollment_api_client = EnrollmentApiClient()
        # Check to see if the user's already enrolled and we have an enterprise course enrollment to track it.
        course_enrollment = enrollment_api_client.get_course_enrollment(self.username, course_run_id) or {}
        enrolled_in_course = course_enrollment and course_enrollment.get('is_active', False)

        audit_modes = getattr(settings, 'ENTERPRISE_COURSE_ENROLLMENT_AUDIT_MODES', ['audit', 'honor'])
        paid_modes = ['verified', 'professional']
        is_upgrading = mode in paid_modes and course_enrollment.get('mode') in audit_modes

        if enrolled_in_course and is_upgrading:
            LOGGER.info(
                "[Enroll] Trying to upgrade the enterprise user [{learner_id}] in course [{course_run_id}] in "
                "[{mode}] mode".format(
                    learner_id=self.id,
                    course_run_id=course_run_id,
                    mode=mode
                )
            )
        if not enrolled_in_course:
            LOGGER.info(
                "[Enroll] Trying to enroll the enterprise user [{learner_id}] in course [{course_run_id}] in "
                "[{mode}] mode".format(
                    learner_id=self.id,
                    course_run_id=course_run_id,
                    mode=mode
                )
            )

        if not enrolled_in_course or is_upgrading:
            if cohort and not self.enterprise_customer.enable_autocohorting:
                raise CourseEnrollmentPermissionError("Auto-cohorting is not enabled for this enterprise")

            try:
                enterprise_course_enrollment, created = EnterpriseCourseEnrollment.objects.get_or_create(
                    enterprise_customer_user=self,
                    course_id=course_run_id,
                    defaults={
                        'source': EnterpriseEnrollmentSource.get_source(source_slug)
                    }
                )
            except IntegrityError:
                # Added to try and fix ENT-2463. This can happen if the user is already a part of the enterprise
                # because of the following:
                # 1. (non-enterprise) CourseEnrollment data is created
                # 2. An async task to is signaled to run after CourseEnrollment creation
                #    (create_enterprise_enrollment_receiver)
                # 3. Both async task and the code in the try block run `get_or_create` on
                # `EnterpriseCourseEnrollment`
                # 4. A race condition happens and it tries to create the same data twice
                # Catching will allow us to continue and ensure we can still create an order for this enrollment.
                LOGGER.exception("IntegrityError on attempt at EnterpriseCourseEnrollment for user with id [%s] "
                                 "and course id [%s]", self.user_id, course_run_id)
            # Directly enroll into the specified track.
            # This should happen after we create the EnterpriseCourseEnrollment
            succeeded = True
            LOGGER.info(
                "[Enroll] Calling LMS enrollment API for user [username] in course [course_run_id] in mode "
                "[mode]".format(
                    username=self.username,
                    course_run_id=course_run_id,
                    mode=mode
                )
            )
            try:
                enrollment_api_client.enroll_user_in_course(self.username, course_run_id, mode, cohort=cohort)
            except HttpClientError as exc:
                succeeded = False
                if created:
                    enterprise_course_enrollment.delete()
                default_message = 'No error message provided'
                try:
                    error_message = json.loads(exc.content.decode()).get('message', default_message)
                except ValueError:
                    error_message = default_message
                LOGGER.exception(
                    'Error while enrolling user %(user)s: %(message)s',
                    dict(user=self.user_id, message=error_message)
                )
            if succeeded:
                utils.track_event(self.user_id, 'edx.bi.user.enterprise.enrollment.course', {
                    'category': 'enterprise',
                    'label': course_run_id,
                    'enterprise_customer_uuid': str(self.enterprise_customer.uuid),
                    'enterprise_customer_name': self.enterprise_customer.name,
                    'mode': mode,
                    'cohort': cohort,
                    'is_upgrading': is_upgrading,
                })
                LOGGER.info(
                    "[Enroll] LMS enrollment API succeeded for user [username] in course [course_run_id] in mode "
                    "[mode]".format(
                        username=self.username,
                        course_run_id=course_run_id,
                        mode=mode
                    )
                )
                if mode in paid_modes:
                    # create an ecommerce order for the course enrollment
                    self.create_order_for_enrollment(course_run_id, discount_percentage, mode, sales_force_id)
        elif enrolled_in_course and course_enrollment.get('mode') in paid_modes and mode in audit_modes:
            # This enrollment is attempting to "downgrade" the user from a paid track they are already in.
            raise CourseEnrollmentDowngradeError(
                'The user is already enrolled in the course {course_run_id} in {current_mode} mode '
                'and cannot be enrolled in {given_mode} mode'.format(
                    course_run_id=course_run_id,
                    current_mode=course_enrollment.get('mode'),
                    given_mode=mode,
                )
            )

    def unenroll(self, course_run_id):
        """
        Unenroll a user from a course track.
        """
        enrollment_api_client = EnrollmentApiClient()
        if enrollment_api_client.unenroll_user_from_course(self.username, course_run_id):
            EnterpriseCourseEnrollment.objects.filter(enterprise_customer_user=self, course_id=course_run_id).delete()
            return True
        return False

    def update_session(self, request):
        """
        Update the session of a request for this learner.
        """
        request.session['enterprise_customer'] = self.enterprise_customer.serialized

    def create_order_for_enrollment(self, course_run_id, discount_percentage, mode, sales_force_id):
        """
        Create an order on the Ecommerce side for tracking the course enrollment of a enterprise customer user.
        """
        LOGGER.info("Creating order for enterprise learner with id [%s] for enrollment in course with id: [%s], "
                    "[percentage discount] [%s] and [sales_force_id] [%s]",
                    self.user_id,
                    course_run_id,
                    discount_percentage,
                    sales_force_id)
        # get instance of the EcommerceApiClient and attempt to create order
        ecommerce_service_worker = get_ecommerce_worker_user()
        failure_log_msg = 'Could not create order for enterprise learner with id [%s] for enrollment in course with ' \
                          'id [%s]. Reason: [%s]'
        if ecommerce_service_worker is not None:
            try:
                ecommerce_api_client = EcommerceApiClient(ecommerce_service_worker)
            except NotConnectedToOpenEdX as exc:
                LOGGER.exception(failure_log_msg, self.user_id, course_run_id, str(exc))
            else:
                # pull data needed for creating the order
                course_enrollments = [{
                    'lms_user_id': self.user_id,
                    'username': self.username,
                    'email': self.user_email,
                    'course_run_key': course_run_id,
                    'mode': mode,
                    "enterprise_customer_name": self.enterprise_customer.name,
                    "enterprise_customer_uuid": str(self.enterprise_customer.uuid),
                    "discount_percentage": float(discount_percentage),
                    "sales_force_id": sales_force_id,
                }]
                ecommerce_api_client.create_manual_enrollment_orders(course_enrollments)
        else:
            LOGGER.warning(failure_log_msg, self.user_id, course_run_id, 'Failed to retrieve a valid ecommerce worker.')

    @classmethod
    def inactivate_other_customers(cls, user_id, enterprise_customer):
        """
        Inactive all the enterprise customers of given user except the given enterprise_customer.
        """
        EnterpriseCustomerUser.objects.filter(
            user_id=user_id
        ).exclude(enterprise_customer=enterprise_customer).update(active=False)


@python_2_unicode_compatible
class PendingEnterpriseCustomerUser(TimeStampedModel):
    # pylint: disable=line-too-long
    """
    Model that stores "future members" of enterprise customer.

    Fields:
        enterprise_customer (ForeignKey[:class:`.EnterpriseCustomer`]): enterprise customer
        user_email (:class:`django.db.models.EmailField`): user email

    .. pii: The user_email field contains PII, but locally deleted via enterprise.signals.handle_user_post_save when the learner registers a new account.  As an additional safety measure, we also delete this row (if found) during user retirement.
    .. pii_types: email_address
    .. pii_retirement: local_api, consumer_api
    """  # pylint: enable=line-too-long

    enterprise_customer = models.ForeignKey(EnterpriseCustomer, blank=False, null=False, on_delete=models.CASCADE)
    user_email = models.EmailField(null=False, blank=False)
    history = HistoricalRecords()

    class Meta:
        app_label = 'enterprise'
        ordering = ['created']
        constraints = [
            models.UniqueConstraint(
                fields=['user_email', 'enterprise_customer'],
                name='unique user and EnterpriseCustomer',
            ),
        ]
        indexes = [
            models.Index(fields=['user_email', 'enterprise_customer']),
            models.Index(fields=['user_email']),
        ]

    def link_pending_enterprise_user(self, user, is_user_created):
        """
        Link a PendingEnterpriseCustomerUser to the appropriate EnterpriseCustomer by
        creating a EnterpriseCustomerUser record.

        Arguments:
            is_user_created: a boolean whether the User instance was created or updated
            user: a User instance

        Returns: an EnterpriseCustomerUser instance
        """
        if not is_user_created:
            # user already existed and may simply be logging in or existing user may have changed
            # their email to match one of pending link records. if an ``EnterpriseCustomerUser``
            # record exists, return it since user is already linked.
            try:
                enterprise_customer_user = EnterpriseCustomerUser.objects.get(
                    user_id=user.id,
                    enterprise_customer=self.enterprise_customer,
                )
                message_template = "User {user} has logged in or changed email to match pending " \
                    "Enterprise Customer link, but was already " \
                    "linked to Enterprise Customer {enterprise_customer} - " \
                    "deleting pending link record"
                LOGGER.info(message_template.format(
                    user=user,
                    enterprise_customer=enterprise_customer_user.enterprise_customer,
                ))
                return enterprise_customer_user
            except EnterpriseCustomerUser.DoesNotExist:
                pass  # nothing to do here

        enterprise_customer_user, __ = EnterpriseCustomerUser.objects.get_or_create(
            enterprise_customer=self.enterprise_customer,
            user_id=user.id,
        )
        return enterprise_customer_user

    def fulfill_pending_course_enrollments(self, enterprise_customer_user):
        """
        Enrolls a newly created EnterpriseCustomerUser in any courses attached to their
        PendingEnterpriseCustomerUser record.

        Arguments:
            enterprise_customer_user: a EnterpriseCustomerUser instance
        """
        pending_enrollments = list(self.pendingenrollment_set.all())
        if pending_enrollments:
            def _complete_user_enrollment():
                """
                Complete an Enterprise User's enrollment.

                EnterpriseCustomers may enroll users in courses before the users themselves
                actually exist in the system; in such a case, the enrollment for each such
                course is finalized when the user registers with the OpenEdX platform.
                """
                for enrollment in pending_enrollments:
                    enterprise_customer_user.enroll(
                        enrollment.course_id,
                        enrollment.course_mode,
                        cohort=enrollment.cohort_name,
                        source_slug=getattr(enrollment.source, 'slug', None),
                        discount_percentage=enrollment.discount_percentage,
                        sales_force_id=enrollment.sales_force_id,
                    )
                    track_enrollment('pending-admin-enrollment', enterprise_customer_user.user.id, enrollment.course_id)
            transaction.on_commit(_complete_user_enrollment)

    def __str__(self):
        """
        Return human-readable string representation.
        """
        return "<PendingEnterpriseCustomerUser {ID}>: {enterprise_name} - {user_email}".format(
            ID=self.id,
            enterprise_name=self.enterprise_customer.name,
            user_email=self.user_email,
        )

    def __repr__(self):
        """
        Return uniquely identifying string representation.
        """
        return self.__str__()


@python_2_unicode_compatible
class EnterpriseEnrollmentSource(TimeStampedModel):
    """
    Define a Name and Source for all Enterprise Enrollment Sources.

    .. no_pii:
    """

    MANUAL = 'manual'
    API = 'enterprise_api'
    ENROLLMENT_URL = 'enrollment_url'
    OFFER_REDEMPTION = 'offer_redemption'
    ENROLLMENT_TASK = 'enrollment_task'
    MANAGEMENT_COMMAND = 'management_command'

    name = models.CharField(max_length=64)
    slug = models.SlugField(max_length=30, unique=True)

    @classmethod
    def get_source(cls, source_slug):
        """
        Retrieve the source based on the Slug provided.
        """
        try:
            return cls.objects.get(slug=source_slug)
        except EnterpriseEnrollmentSource.DoesNotExist:
            return None

    def __str__(self):
        """
        Create string representation of the source.
        """
        return "Enrollment Source: {name}, Slug: {slug}".format(name=self.name, slug=self.slug)


@python_2_unicode_compatible
class PendingEnrollment(TimeStampedModel):
    """
    Track future enrollments for PendingEnterpriseCustomerUser.

    Store a course ID, an intended enrollment mode, and a link to a PendingEnterpriseCustomerUser;
    when the PendingEnterpriseCustomerUser is converted to a full EnterpriseCustomerUser, API
    calls will be made to enroll the newly-created user in whatever courses have been added.

    .. no_pii:
    """

    user = models.ForeignKey(PendingEnterpriseCustomerUser, null=False, on_delete=models.deletion.CASCADE)
    course_id = models.CharField(max_length=255, blank=False,)
    course_mode = models.CharField(max_length=25, blank=False)
    cohort_name = models.CharField(max_length=255, blank=True, null=True)
    discount_percentage = models.DecimalField(default=0.0, max_digits=8, decimal_places=5)
    sales_force_id = models.CharField(max_length=255, blank=True, null=True)
    history = HistoricalRecords()
    source = models.ForeignKey(EnterpriseEnrollmentSource, blank=False, null=True, on_delete=models.SET_NULL)

    class Meta:
        app_label = 'enterprise'
        unique_together = (("user", "course_id"),)
        ordering = ['created']

    def __str__(self):
        """
        Create string representation of the enrollment.
        """
        return '<PendingEnrollment for email {} in course with ID {}>'.format(self.user.user_email, self.course_id)

    def __repr__(self):
        """
        Return string representation of the enrollment.
        """
        return self.__str__()


def logo_path(instance, filename):
    """
    Delete the file if it already exist and returns the enterprise customer logo image path.

    Arguments:
        instance (:class:`.EnterpriseCustomerBrandingConfiguration`): EnterpriseCustomerBrandingConfiguration object
        filename (str): file to upload

    Returns:
        path: path of image file e.g. enterprise/branding/<model.id>/<model_id>_logo.<ext>.lower()

    """
    extension = os.path.splitext(filename)[1].lower()
    instance_id = str(instance.id)
    fullname = os.path.join("enterprise/branding/", instance_id, instance_id + "_logo" + extension)
    if default_storage.exists(fullname):
        default_storage.delete(fullname)
    return fullname


@python_2_unicode_compatible
class EnterpriseCustomerBrandingConfiguration(TimeStampedModel):
    """
    Model that keeps track of enterprise branding configurations e.g. enterprise customer logo.

    Fields:
        enterprise_customer (ForeignKey[EnterpriseCustomer]): enterprise customer
        logo (ImageField): enterprise customer image

    .. no_pii:
    """

    enterprise_customer = models.OneToOneField(
        EnterpriseCustomer,
        blank=False,
        null=False,
        related_name="branding_configuration",
        on_delete=models.deletion.CASCADE
    )
    logo = models.ImageField(
        upload_to=logo_path,
        help_text=_(u"Logo images must be in .png format."),
        null=True, blank=True, max_length=255,
        validators=[validate_image_extension, validate_image_size]
    )
    primary_color = models.CharField(
        null=True,
        blank=True,
        max_length=7,
        validators=[validate_hex_color],
    )
    secondary_color = models.CharField(
        null=True,
        blank=True,
        max_length=7,
        validators=[validate_hex_color],
    )
    tertiary_color = models.CharField(
        null=True,
        blank=True,
        max_length=7,
        validators=[validate_hex_color],
    )

    class Meta:
        """Meta class for this Django model."""

        app_label = 'enterprise'
        verbose_name = _("Branding Configuration")
        verbose_name_plural = _("Branding Configurations")
        ordering = ['created']

    def __str__(self):
        """
        Return human-readable string representation.
        """
        return "<EnterpriseCustomerBrandingConfiguration {ID}>: {enterprise_name}".format(
            ID=self.id,
            enterprise_name=self.enterprise_customer.name,
        )

    def __repr__(self):
        """
        Return uniquely identifying string representation.
        """
        return self.__str__()

    @property
    def safe_logo_url(self):
        """
        Returns an absolute URL for the branding configuration logo OR the platform logo absolute URL
        """
        if not self.logo:
            return get_platform_logo_url()

        # AWS S3 storage is used in stage/production environments but file system
        # storage is used in devstack environment
        if settings.DEFAULT_FILE_STORAGE == 'storages.backends.s3boto.S3BotoStorage':
            media_base_url = 'https://' + settings.AWS_S3_CUSTOM_DOMAIN
        else:
            media_base_url = settings.LMS_ROOT_URL + settings.MEDIA_URL

        return urljoin(
            media_base_url,
            str(self.logo)
        )


@python_2_unicode_compatible
class EnterpriseCustomerIdentityProvider(TimeStampedModel):
    """
    EnterpriseCustomerIdentityProvider is a One to Many relationship between Enterprise Customer and Identity Provider.

    There should be a link between an enterprise customer and its Identity Provider. This relationship has
    following constraints
        1. An enterprise customer may or may not have an identity provider.
        2. An enterprise customer can have more than one identity providers.
        3. Enterprise customer site should match with identity provider's site. (i.e. same domain names)

    Fields:
        enterprise_customer (ForeignKey[EnterpriseCustomer]): enterprise customer
        provider_id (:class:`django.db.models.SlugField`): The provider_id string of the identity provider.

    .. no_pii:
    """

    enterprise_customer = models.ForeignKey(
        EnterpriseCustomer,
        blank=False,
        null=False,
        related_name="enterprise_customer_identity_providers", on_delete=models.CASCADE
    )
    provider_id = models.SlugField(
        null=False,
        blank=False,
        unique=True,
        help_text="Slug field containing a unique identifier for the identity provider.",
    )

    class Meta:
        app_label = 'enterprise'
        ordering = ['created']

    def __str__(self):
        """
        Return human-readable string representation.
        """
        return "<EnterpriseCustomerIdentityProvider {provider_id}>: {enterprise_name}".format(
            provider_id=self.provider_id,
            enterprise_name=self.enterprise_customer.name,
        )

    def __repr__(self):
        """
        Return uniquely identifying string representation.
        """
        return self.__str__()

    @property
    def identity_provider(self):
        """
        Associated identity provider instance.
        """
        identity_provider = utils.get_identity_provider(self.provider_id)
        return identity_provider

    @property
    def provider_name(self):
        """
        Readable name for the identity provider.
        """
        identity_provider = self.identity_provider
        return identity_provider and identity_provider.name

    @property
    def sync_learner_profile_data(self):
        """
        Return bool indicating if data received from the identity provider shoudl be synced to the edX profile.
        """
        identity_provider = self.identity_provider
        return identity_provider is not None and identity_provider.sync_learner_profile_data


class EnterpriseCourseEnrollmentManager(models.Manager):
    """
    Model manager for `EnterpriseCourseEnrollment`.
    """

    def get_queryset(self):
        """
        Override to return only those enrollment records for which learner is linked to an enterprise.
        """
        return super().get_queryset().select_related('enterprise_customer_user').filter(
            enterprise_customer_user__linked=True
        )


@python_2_unicode_compatible
class EnterpriseCourseEnrollment(TimeStampedModel):
    """
    Store information about the enrollment of a user in a course.

    This model is the central source of truth for information about
    whether a particular user, linked to a particular EnterpriseCustomer,
    has been enrolled in a course, and is the repository for any other
    relevant metadata about such an enrollment.

    Do not delete records of this model - there are downstream business
    reporting processes that rely them, even if the underlying ``student.CourseEnrollment``
    record has been marked inactive/un-enrolled.  As a consequence, the only
    way to determine if a given ``EnterpriseCourseEnrollment`` is currently active
    is to examine the ``is_active`` field of the associated ``student.CourseEnrollment``.

    .. no_pii:
    """

    objects = EnterpriseCourseEnrollmentManager()

    class Meta:
        unique_together = (('enterprise_customer_user', 'course_id',),)
        app_label = 'enterprise'
        ordering = ['created']

    enterprise_customer_user = models.ForeignKey(
        EnterpriseCustomerUser,
        blank=False,
        null=False,
        related_name='enterprise_enrollments',
        on_delete=models.deletion.CASCADE,
        help_text=_(
            "The enterprise learner to which this enrollment is attached."
        )
    )
    course_id = models.CharField(
        max_length=255,
        blank=False,
        help_text=_(
            "The ID of the course in which the learner was enrolled."
        )
    )
    saved_for_later = models.BooleanField(
        default=False,
        blank=False,
        help_text=_(
            "Specifies whether a user marked this course as saved for later in the learner portal."
        )
    )
    history = HistoricalRecords()
    source = models.ForeignKey(
        EnterpriseEnrollmentSource,
        blank=False,
        null=True,
        on_delete=models.SET_NULL
    )

    @property
    def audit_reporting_disabled(self):
        """
        Specify whether audit track data reporting is disabled for this enrollment.

        * If the enterprise customer associated with this enrollment enables audit track data reporting,
          simply return False.
        * If the enterprise customer associated with this enrollment does not enable audit track data reporting,
          return True if we are dealing with an audit enrollment, and False otherwise.

        :return: True if audit track data reporting is disabled, False otherwise.
        """
        if not self.enterprise_customer_user.enterprise_customer.enables_audit_data_reporting:
            return self.is_audit_enrollment

        # Since audit data reporting is enabled, we always return False here.
        return False

    @property
    def is_audit_enrollment(self):
        """
        Specify whether the course enrollment associated with this ``EnterpriseCourseEnrollment`` is in audit mode.

        :return: Whether the course enrollment mode is of an audit type.
        """
        course_enrollment_api = EnrollmentApiClient()
        course_enrollment = course_enrollment_api.get_course_enrollment(
            self.enterprise_customer_user.username,
            self.course_id
        )
        audit_modes = getattr(settings, 'ENTERPRISE_COURSE_ENROLLMENT_AUDIT_MODES', ['audit', 'honor'])
        return course_enrollment and course_enrollment.get('mode') in audit_modes

    @property
    def license(self):
        """
        Returns the license associated with this enterprise course enrollment if one exists.
        """
        try:
            associated_license = self.licensed_with  # pylint: disable=no-member
        except LicensedEnterpriseCourseEnrollment.DoesNotExist:
            associated_license = None
        return associated_license

    @cached_property
    def course_enrollment(self):
        """
        Returns the ``student.CourseEnrollment`` associated with this enterprise course enrollment record.
        """
        if not CourseEnrollment:
            return None
        try:
            return CourseEnrollment.objects.get(
                user=self.enterprise_customer_user.user,
                course_id=self.course_id,
            )
        except CourseEnrollment.DoesNotExist:
            LOGGER.error('{} does not have a matching student.CourseEnrollment'.format(self))
            return None

    @property
    def is_active(self):
        """
        Returns True iff this enrollment is currently active.
        """
        return self.course_enrollment.is_active

    @property
    def mode(self):
        """
        Returns the mode of the ``student.CourseEnrollment`` associated with this enterprise course enrollment record.
        """
        return self.course_enrollment.mode

    @classmethod
    def get_enterprise_course_enrollment_id(cls, user, course_id, enterprise_customer):
        """
        Return the EnterpriseCourseEnrollment object for a given user in given course_id.
        """
        enterprise_course_enrollment_id = None
        try:
            enterprise_course_enrollment_id = cls.objects.get(
                enterprise_customer_user=EnterpriseCustomerUser.objects.get(
                    enterprise_customer=enterprise_customer,
                    user_id=user.id
                ),
                course_id=course_id
            ).id
        except ObjectDoesNotExist:
            LOGGER.info(
                'EnterpriseCourseEnrollment entry not found for user: {username}, course: {course_id}, '
                'enterprise_customer: {enterprise_customer_name}'.format(
                    username=user.username,
                    course_id=course_id,
                    enterprise_customer_name=enterprise_customer.name
                )
            )
        return enterprise_course_enrollment_id

    @classmethod
    def get_enterprise_uuids_with_user_and_course(cls, user_id, course_run_id, active=None):
        """
        Returns a list of UUID(s) for EnterpriseCustomer(s) that this enrollment
        links together with the user_id and course_run_id
        """
        try:
            queryset = cls.objects.filter(
                course_id=course_run_id,
                enterprise_customer_user__user_id=user_id
            )
            if active is not None:
                queryset = queryset.filter(
                    enterprise_customer_user__enterprise_customer__active=active
                )

            linked_enrollments = queryset.select_related(
                'enterprise_customer_user',
                'enterprise_customer_user__enterprise_customer',
            )
            return [str(le.enterprise_customer_user.enterprise_customer.uuid) for le in linked_enrollments]

        except ObjectDoesNotExist:
            LOGGER.info(
                'EnterpriseCustomerUser entries not found for user id: {username}, course: {course_run_id}.'
                .format(
                    username=user_id,
                    course_run_id=course_run_id
                )
            )
            return []

    def __str__(self):
        """
        Create string representation of the enrollment.
        """
        return '<EnterpriseCourseEnrollment for user {} in course with ID {}>'.format(
            self.enterprise_customer_user.user.username,
            self.course_id
        )

    def __repr__(self):
        """
        Return string representation of the enrollment.
        """
        return self.__str__()


class LicensedEnterpriseCourseEnrollment(TimeStampedModel):
    """
    An Enterprise Course Enrollment that is enrolled via a license.

    .. no_pii:
    """

    license_uuid = models.UUIDField(
        primary_key=False,
        editable=False,
        null=False
    )

    enterprise_course_enrollment = models.OneToOneField(
        EnterpriseCourseEnrollment,
        blank=False,
        null=False,
        related_name='licensed_with',
        on_delete=models.deletion.CASCADE,
        help_text=_(
            "The course enrollment the associated license is for."
        )
    )

    is_revoked = models.BooleanField(
        default=False,
        help_text=_(
            "Whether the licensed enterprise course enrollment is revoked, e.g., when a user's license is revoked."
        )
    )

    history = HistoricalRecords()

    @classmethod
    def enrollments_for_user(cls, enterprise_customer_user):
        """
        Returns a QuerySet of LicensedEnterpriseCourseEnrollments, along with their associated (hydrated)
        enterprise enrollments, users, and customers.
        """
        return cls.objects.filter(
            enterprise_course_enrollment__enterprise_customer_user=enterprise_customer_user
        ).select_related(
            'enterprise_course_enrollment',
            'enterprise_course_enrollment__enterprise_customer_user',
            'enterprise_course_enrollment__enterprise_customer_user__enterprise_customer',
        )

    def revoke(self):
        """
        Marks this object as revoked and marks the associated EnterpriseCourseEnrollment
        as "saved for later".  This object and the associated EnterpriseCourseEnrollment are both saved.
        """
        self.is_revoked = True
        self.enterprise_course_enrollment.saved_for_later = True
        self.enterprise_course_enrollment.save()
        self.save()


@python_2_unicode_compatible
class EnterpriseCatalogQuery(TimeStampedModel):
    """
    Stores a re-usable catalog query.

    This stored catalog query used in `EnterpriseCustomerCatalog` objects to build catalog's content_filter field.
    This is a saved instance of `content_filter` that can be re-used accross different catalogs.

    .. no_pii:
    """

    title = models.CharField(
        default='All Content',
        max_length=255,
        blank=False,
        null=False
    )
    content_filter = JSONField(
        default={},
        blank=True,
        null=True,
        load_kwargs={'object_pairs_hook': collections.OrderedDict},
        dump_kwargs={'indent': 4, 'cls': JSONEncoder, 'separators': (',', ':')},
        help_text=_(
            "Query parameters which will be used to filter the discovery service's search/all endpoint results, "
            "specified as a JSON object. An empty JSON object means that all available content items will be "
            "included in the catalog."
        ),
        validators=[validate_content_filter_fields]
    )

    class Meta:
        verbose_name = _("Enterprise Catalog Query")
        verbose_name_plural = _("Enterprise Catalog Queries")
        app_label = 'enterprise'
        ordering = ['created']

    def __str__(self):
        """
        Return human-readable string representation.
        """
        return "<EnterpriseCatalogQuery '{title}' >".format(title=self.title)


@python_2_unicode_compatible
class EnterpriseCustomerCatalog(TimeStampedModel):
    """
    Store catalog information from course discovery specifically for Enterprises.

    We use this model to consolidate course catalog information, which includes
    information about catalogs, courses, programs, and possibly more in the
    future, as the course discovery service evolves.

    .. no_pii:
    """

    uuid = models.UUIDField(
        primary_key=True,
        default=uuid4,
        editable=False
    )
    title = models.CharField(
        default='All Content',
        max_length=255,
        blank=False,
        null=False
    )
    enterprise_customer = models.ForeignKey(
        EnterpriseCustomer,
        blank=False,
        null=False,
        related_name='enterprise_customer_catalogs',
        on_delete=models.deletion.CASCADE
    )
    sync_enterprise_catalog_query = models.BooleanField(
        default=False
    )
    enterprise_catalog_query = models.ForeignKey(
        EnterpriseCatalogQuery,
        blank=True,
        null=True,
        related_name='enterprise_customer_catalogs',
        on_delete=models.deletion.SET_NULL
    )
    content_filter = JSONField(
        default={},
        blank=True,
        null=True,
        load_kwargs={'object_pairs_hook': collections.OrderedDict},
        dump_kwargs={'indent': 4, 'cls': JSONEncoder, 'separators': (',', ':')},
        help_text=_(
            "Query parameters which will be used to filter the discovery service's search/all endpoint results, "
            "specified as a Json object. An empty Json object means that all available content items will be "
            "included in the catalog."
        ),
        validators=[validate_content_filter_fields]
    )
    enabled_course_modes = JSONField(
        default=json_serialized_course_modes,
        help_text=_('Ordered list of enrollment modes which can be displayed to learners for course runs in'
                    ' this catalog.'),
    )
    publish_audit_enrollment_urls = models.BooleanField(
        default=False,
        help_text=_(
            "Specifies whether courses should be published with direct-to-audit enrollment URLs."
        )
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = _("Enterprise Customer Catalog")
        verbose_name_plural = _("Enterprise Customer Catalogs")
        app_label = 'enterprise'
        ordering = ['created']

    def __str__(self):
        """
        Return human-readable string representation.
        """
        return (
            "<EnterpriseCustomerCatalog '{title}' "
            "with UUID '{uuid}' "
            "for EnterpriseCustomer {enterprise_customer_name}>".format(
                title=self.title,
                uuid=self.uuid,
                enterprise_customer_name=self.enterprise_customer.name
            )
        )

    def __repr__(self):
        """
        Return uniquely identifying string representation.
        """
        return self.__str__()

    def get_content_filter(self):
        """
        Return content filter of the linked catalog query otherwise content filter of catalog itself.
        """
        return self.enterprise_catalog_query.content_filter if self.enterprise_catalog_query else self.content_filter

    @cached_property
    def content_filter_ids(self):
        """
        Return the list of any content IDs specified in the catalog's content filter.
        """
        content_filter = self.get_content_filter()
        return set(content_filter.get('key', []) + content_filter.get('uuid', []))

    def get_paginated_content(self, query_parameters):
        """
        Return paginated discovery service search results without expired course runs.

        Arguments:
            query_parameters (dict): Additional query parameters to add to the search API call, e.g. page.
        Returns:
            dict: The paginated discovery service search results.
        """
        query_params = query_parameters.copy()
        # exclude_expired_course_run query_param is added to remove the expired course run
        query_params["exclude_expired_course_run"] = True
        results = []
        content_filter_query = self.get_content_filter().copy()
        catalog_client = get_course_catalog_api_service_client(self.enterprise_customer.site)
        search_results = catalog_client.get_catalog_results(content_filter_query, query_params.dict())
        for content in search_results['results']:
            if content['content_type'] == 'courserun' and content['has_enrollable_seats']:
                results.append(content)
            elif content['content_type'] == 'course':
                results.append(content)
            elif content['content_type'] == 'program' and content['is_program_eligible_for_one_click_purchase']:
                results.append(content)

        response = {
            'count': search_results['count'],
            'next': search_results['next'],
            'previous': search_results['previous'],
            'results': results,
        }

        return response

    def _filter_members(self, content_id_field_name, content_id_values):
        """
        Filter the given list of content_id_values, returning only those that are members of the catalog.

        A content ID is the unique identifier for a content metadata entity, e.g. course, course run, program.

        Arguments:
            content_id_field_name (str): The name of the field on the catalog content item
                                         that stores the item's unique identifier, e.g. "key", "uuid".
            content_id_values (list): If provided, return only the content IDs that are members of this list
                                      and members of the catalog.

        Returns:
            list: The list of content IDs that are members of the catalog.
        """
        updated_content_filter = self.get_content_filter().copy()
        updated_content_filter[content_id_field_name] = content_id_values
        response = get_course_catalog_api_service_client(self.enterprise_customer.site).get_catalog_results(
            updated_content_filter,
            traverse_pagination=True
        )
        results = response.get('results', [])
        return {x[content_id_field_name] for x in results}

    def contains_courses(self, content_ids):
        """
        Return True if this catalog contains the given courses else False.

        The content_ids parameter should be a list containing course keys
        and/or course run ids.
        """
        # Translate any provided course run IDs to course keys.
        catalog_client = get_course_catalog_api_service_client(self.enterprise_customer.site)
        course_keys = {catalog_client.get_course_id(k) for k in content_ids}

        # Remove `None` from set of course_keys if present
        course_keys = course_keys.difference({None})

        content_ids_in_catalog = self.content_filter_ids
        if not content_ids_in_catalog:
            content_ids_in_catalog = self._filter_members('key', list(course_keys)) if course_keys else set()

        return bool(
            (content_ids and set(content_ids).issubset(content_ids_in_catalog)) or
            (course_keys and course_keys.issubset(content_ids_in_catalog))
        )

    def contains_programs(self, program_uuids):
        """
        Return true if this catalog contains the given programs.
        """
        content_ids_in_catalog = self.content_filter_ids
        if not content_ids_in_catalog:
            content_ids_in_catalog = self._filter_members('uuid', program_uuids)

        return bool(program_uuids and set(program_uuids).issubset(content_ids_in_catalog))

    def get_course(self, course_key):
        """
        Get all of the metadata for the given course.

        Arguments:
            course_key (str): The course key which identifies the course.

        Return:
            dict: The course metadata.
        """
        if not EnterpriseCatalogApiClient().contains_content_items(self.uuid, [course_key]):
            return None

        return get_course_catalog_api_service_client(self.enterprise_customer.site).get_course_details(course_key)

    def get_course_run(self, course_run_id):
        """
        Get all of the metadata for the given course run.

        Arguments:
            course_run_id (str): The course run key which identifies the course run.

        Return:
            dict: The course run metadata.
        """
        if not EnterpriseCatalogApiClient().contains_content_items(self.uuid, [course_run_id]):
            return None

        return get_course_catalog_api_service_client(self.enterprise_customer.site).get_course_run(course_run_id)

    def get_course_and_course_run(self, course_run_id):
        """
        Get course data and all of the metadata for the given course run.

        Arguments:
            course_run_id (str): The course run key which identifies the course run.

        Returns:
            tuple(course, course_run): The course and course run metadata.

        Raises:
            ImproperlyConfigured: Missing or invalid catalog integration.

        """
        if not EnterpriseCatalogApiClient().contains_content_items(self.uuid, [course_run_id]):
            return None, None

        return get_course_catalog_api_service_client(
            self.enterprise_customer.site
        ).get_course_and_course_run(course_run_id)

    def get_program(self, program_uuid):
        """
        Get all of the metadata for the given program.

        Arguments:
            program_uuid (str): The program UUID which identifies the program.

        Return:
            dict: The program metadata.
        """
        if not EnterpriseCatalogApiClient().contains_content_items(self.uuid, [program_uuid]):
            return None

        return get_course_catalog_api_service_client(self.enterprise_customer.site).get_program_by_uuid(program_uuid)

    def get_course_enrollment_url(self, course_key):
        """
        Return enterprise course enrollment page url with the catalog information for the given course.

        Arguments:
            course_key (str): The course key for the course to be displayed.

        Returns:
            (str): Enterprise landing page url.
        """
        url = self.enterprise_customer.get_course_enrollment_url(course_key)
        if self.publish_audit_enrollment_urls:
            url = utils.update_query_parameters(url, {'audit': 'true'})

        return utils.update_query_parameters(url, {'catalog': self.uuid})

    def get_course_run_enrollment_url(self, course_run_key):
        """
        Return enterprise course enrollment page url with the catalog information for the given course.

        Arguments:
            course_run_key (str): The course run id for the course to be displayed.

        Returns:
            (str): Enterprise landing page url.
        """
        url = self.enterprise_customer.get_course_run_enrollment_url(course_run_key)
        if self.publish_audit_enrollment_urls:
            url = utils.update_query_parameters(url, {'audit': 'true'})

        return utils.update_query_parameters(url, {'catalog': self.uuid})

    def get_program_enrollment_url(self, program_uuid):
        """
        Return enterprise program enrollment page url with the catalog information for the given program.

        Arguments:
            program_uuid (str): The program UUID.

        Returns:
            (str): Enterprise program landing page url.
        """
        url = self.enterprise_customer.get_program_enrollment_url(program_uuid)
        if self.publish_audit_enrollment_urls:
            url = utils.update_query_parameters(url, {'audit': 'true'})

        return utils.update_query_parameters(url, {'catalog': self.uuid})

    def save(self, *args, **kwargs):  # pylint: disable=arguments-differ
        """
        Saves this ``EnterpriseCatalogQuery``.

        Copies the ``content_filter`` of a related CatalogQuery into this
        instance's ``content_filter`` if syncing is allowed.
        """
        if self.enterprise_catalog_query and self.sync_enterprise_catalog_query:
            content_filter_from_query = self.enterprise_catalog_query.content_filter
            self.content_filter = content_filter_from_query
        super().save(*args, **kwargs)


@python_2_unicode_compatible
class EnrollmentNotificationEmailTemplate(TimeStampedModel):
    """
    Store optional templates to use when emailing users about course enrollment events.

    .. no_pii:
    """

    class Meta:
        app_label = 'enterprise'
        ordering = ['created']

    BODY_HELP_TEXT = mark_safe_lazy(_(
        'Fill in a standard Django template that, when rendered, produces the email you want '
        'sent to newly-enrolled Enterprise Customer learners. The following variables may be available:\n'
        '<ul><li>user_name: A human-readable name for the person being emailed. Be sure to '
        'handle the case where this is not defined, as it may be missing in some cases. '
        'It may also be a username, if the learner hasn\'t configured their "real" name in the system.</li>'
        '    <li>organization_name: The name of the organization sponsoring the enrollment.</li>'
        '    <li>enrolled_in: Details of the course or program that was enrolled in. It may contain:'
        '    <ul><li>name: The name of the enrollable item (e.g., "Demo Course").</li>'
        '        <li>url: A link to the homepage of the enrolled-in item.</li>'
        '        <li>branding: A custom branding name for the enrolled-in item. For example, '
        'the branding of a MicroMasters program would be "MicroMasters".</li>'
        '     <li>start: The date the enrolled-in item becomes available. Render this to text using the Django `date`'
        ' template filter (see <a href="https://docs.djangoproject.com/en/1.8/ref/templates/'
        'builtins/#date">the Django documentation</a>).</li>'
        '<li>type: Whether the enrolled-in item is a course, a program, or something else.</li></ul></ul>'
    ))

    SUBJECT_HELP_TEXT = _(
        'Enter a string that can be used to generate a dynamic subject line for notification emails. The '
        'placeholder {course_name} will be replaced with the name of the course or program that was enrolled in.'
    )

    plaintext_template = models.TextField(blank=True, help_text=BODY_HELP_TEXT)
    html_template = models.TextField(blank=True, help_text=BODY_HELP_TEXT)
    subject_line = models.CharField(max_length=100, blank=True, help_text=SUBJECT_HELP_TEXT)
    enterprise_customer = models.OneToOneField(
        EnterpriseCustomer,
        related_name="enterprise_enrollment_template",
        on_delete=models.deletion.CASCADE
    )
    history = HistoricalRecords()

    def render_html_template(self, kwargs):
        """
        Render just the HTML template and return it as a string.
        """
        return self.render_template(mark_safe(self.html_template), kwargs)

    def render_plaintext_template(self, kwargs):
        """
        Render just the plaintext template and return it as a string.
        """
        return self.render_template(self.plaintext_template, kwargs)

    def render_all_templates(self, kwargs):
        """
        Render both templates and return both.
        """
        return self.render_plaintext_template(kwargs), self.render_html_template(kwargs)

    def render_template(self, template_text, kwargs):
        """
        Create a template from the DB-backed text and render it.
        """
        template = Template(template_text)
        context = Context(kwargs)
        return template.render(context)

    def __str__(self):
        """
        Return human-readable string representation.
        """
        return '<EnrollmentNotificationEmailTemplate for EnterpriseCustomer with UUID {}>'.format(
            self.enterprise_customer.uuid
        )

    def __repr__(self):
        """
        Return uniquely identifying string representation.
        """
        return self.__str__()


@python_2_unicode_compatible
class EnterpriseCustomerReportingConfiguration(TimeStampedModel):
    """
    The Enterprise's configuration for sending automated data reports securely via email to the Enterprise Admin.

    .. no_pii:
    """

    FREQUENCY_TYPE_DAILY = 'daily'
    FREQUENCY_TYPE_MONTHLY = 'monthly'
    FREQUENCY_TYPE_WEEKLY = 'weekly'
    FREQUENCY_CHOICES = (
        (FREQUENCY_TYPE_DAILY, FREQUENCY_TYPE_DAILY),
        (FREQUENCY_TYPE_MONTHLY, FREQUENCY_TYPE_MONTHLY),
        (FREQUENCY_TYPE_WEEKLY, FREQUENCY_TYPE_WEEKLY),
    )

    DELIVERY_METHOD_EMAIL = 'email'
    DELIVERY_METHOD_SFTP = 'sftp'
    DELIVERY_METHOD_CHOICES = (
        (DELIVERY_METHOD_EMAIL, DELIVERY_METHOD_EMAIL),
        (DELIVERY_METHOD_SFTP, DELIVERY_METHOD_SFTP),
    )

    DATA_TYPE_PROGRESS = 'progress'  # Refers to gathering progress data from Vertica (to be deprecated)
    DATA_TYPE_PROGRESS_V2 = 'progress_v2'  # Refers to gathering progress data from the Analytics Data API
    DATA_TYPE_CATALOG = 'catalog'
    DATA_TYPE_ENGAGEMENT = 'engagement'  # Refers to gathering engagement data from the Analytics Data API
    DATA_TYPE_GRADE = 'grade'
    DATA_TYPE_COMPLETION = 'completion'
    DATA_TYPE_COURSE_STRUCTURE = 'course_structure'
    DATA_TYPE_CHOICES = (
        (DATA_TYPE_PROGRESS, DATA_TYPE_PROGRESS),
        (DATA_TYPE_PROGRESS_V2, DATA_TYPE_PROGRESS_V2),
        (DATA_TYPE_CATALOG, DATA_TYPE_CATALOG),
        (DATA_TYPE_ENGAGEMENT, DATA_TYPE_ENGAGEMENT),
        (DATA_TYPE_GRADE, DATA_TYPE_GRADE),
        (DATA_TYPE_COMPLETION, DATA_TYPE_COMPLETION),
        (DATA_TYPE_COURSE_STRUCTURE, DATA_TYPE_COURSE_STRUCTURE),

    )

    # These types are only valid for the enterprise customer named `Pearson`. We are adding these Reports temporarily
    # and will be reverted after Aurora based reports will be available.
    PEARSON_ONLY_REPORTS = (DATA_TYPE_GRADE, DATA_TYPE_COMPLETION, DATA_TYPE_COURSE_STRUCTURE,)

    REPORT_TYPE_CSV = 'csv'
    REPORT_TYPE_JSON = 'json'
    REPORT_TYPE_CHOICES = (
        (REPORT_TYPE_CSV, REPORT_TYPE_CSV),
        (REPORT_TYPE_JSON, REPORT_TYPE_JSON),
    )

    DAYS_OF_WEEK = (
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    )
    uuid = models.UUIDField(default=uuid4, unique=True)
    enterprise_customer = models.ForeignKey(
        EnterpriseCustomer,
        related_name="reporting_configurations",
        on_delete=models.deletion.CASCADE,
        blank=False,
        null=False,
        verbose_name=_("Enterprise Customer")
    )
    active = models.BooleanField(blank=False, null=False, verbose_name=_("Active"))
    include_date = models.BooleanField(blank=False, default=True, null=False, verbose_name=_("Include Date"),
                                       help_text=_('Include date in the report file name'))
    delivery_method = models.CharField(
        max_length=20,
        choices=DELIVERY_METHOD_CHOICES,
        blank=False,
        default=DELIVERY_METHOD_EMAIL,
        verbose_name=_("Delivery Method"),
        help_text=_("The method in which the data should be sent.")
    )
    pgp_encryption_key = models.TextField(
        null=True,
        blank=True,
        verbose_name=_("PGP Encryption Key"),
        help_text=_('The key for encryption, if PGP encrypted file is required.')
    )
    data_type = models.CharField(
        max_length=20,
        choices=DATA_TYPE_CHOICES,
        blank=False,
        default=DATA_TYPE_PROGRESS,
        verbose_name=_("Data Type"),
        help_text=_("The type of data this report should contain.")
    )
    report_type = models.CharField(
        max_length=20,
        choices=REPORT_TYPE_CHOICES,
        blank=False,
        default=REPORT_TYPE_CSV,
        verbose_name=_("Report Type"),
        help_text=_("The type this report should be sent as, e.g. CSV.")
    )
    email = MultiEmailField(
        blank=True,
        verbose_name=_("Email"),
        help_text=_("The email(s), one per line, where the report should be sent.")
    )
    frequency = models.CharField(
        max_length=20,
        choices=FREQUENCY_CHOICES,
        blank=False,
        default=FREQUENCY_TYPE_MONTHLY,
        verbose_name=_("Frequency"),
        help_text=_("The frequency interval (daily, weekly, or monthly) that the report should be sent."),
    )
    day_of_month = models.SmallIntegerField(
        blank=True,
        null=True,
        verbose_name=_("Day of Month"),
        help_text=_("The day of the month to send the report. "
                    "This field is required and only valid when the frequency is monthly."),
        validators=[MinValueValidator(1), MaxValueValidator(31)]
    )
    day_of_week = models.SmallIntegerField(
        blank=True,
        null=True,
        choices=DAYS_OF_WEEK,
        verbose_name=_("Day of Week"),
        help_text=_("The day of the week to send the report. "
                    "This field is required and only valid when the frequency is weekly."),
    )
    hour_of_day = models.SmallIntegerField(
        verbose_name=_("Hour of Day"),
        help_text=_("The hour of the day to send the report, in Eastern Standard Time (EST). "
                    "This is required for all frequency settings."),
        validators=[MinValueValidator(0), MaxValueValidator(23)]
    )
    decrypted_password = EncryptedCharField(
        max_length=256,
        blank=True,
        null=True,
        help_text=_("This password will be used to secure the zip file. "
                    "It will be encrypted when stored in the database."),
    )
    sftp_hostname = models.CharField(
        max_length=256,
        blank=True,
        null=True,
        verbose_name=_("SFTP Host name"),
        help_text=_("If the delivery method is sftp, the host to deliver the report to.")
    )
    sftp_port = models.PositiveIntegerField(
        blank=True,
        null=True,
        verbose_name=_("SFTP Port"),
        help_text=_("If the delivery method is sftp, the port on the host to connect to."),
        default=22,
    )
    sftp_username = models.CharField(
        max_length=256,
        blank=True,
        null=True,
        verbose_name=_("SFTP username"),
        help_text=_("If the delivery method is sftp, the username to use to securely access the host.")
    )
    decrypted_sftp_password = EncryptedCharField(
        max_length=256,
        blank=True,
        null=True,
        help_text=_("If the delivery method is sftp, the password to use to securely access the host. "
                    "The password will be encrypted when stored in the database."),
    )
    sftp_file_path = models.CharField(
        max_length=256,
        blank=True,
        null=True,
        verbose_name=_("SFTP file path"),
        help_text=_("If the delivery method is sftp, the path on the host to deliver the report to.")
    )
    enterprise_customer_catalogs = models.ManyToManyField(
        EnterpriseCustomerCatalog,
        verbose_name=_("Enterprise Customer Catalogs"),
    )

    class Meta:
        app_label = 'enterprise'
        ordering = ['created']

    @property
    def encrypted_password(self):
        """
        Return encrypted password as a string.

        The data is encrypted in the DB at rest, but is unencrypted in the app when retrieved through the
        decrypted_password field. This method will encrypt the password again before sending.
        """
        if self.decrypted_password:
            return force_text(
                self._meta.get_field('decrypted_password').fernet.encrypt(
                    force_bytes(self.decrypted_password)
                )
            )
        return self.decrypted_password

    @encrypted_password.setter
    def encrypted_password(self, value):
        """
        Set the encrypted password.
        """
        self.decrypted_password = value

    @property
    def encrypted_sftp_password(self):
        """
        Return encrypted SFTP password as a string.

        The data is encrypted in the DB at rest, but is unencrypted in the app when retrieved through the
        decrypted_password field. This method will encrypt the password again before sending.
        """
        if self.decrypted_sftp_password:
            return force_text(
                self._meta.get_field('decrypted_sftp_password').fernet.encrypt(
                    force_bytes(self.decrypted_sftp_password)
                )
            )
        return self.decrypted_sftp_password

    @encrypted_sftp_password.setter
    def encrypted_sftp_password(self, value):
        """
        Set the encrypted SFTP password.
        """
        self.decrypted_sftp_password = value

    def __str__(self):
        """
        Return human-readable string representation.
        """
        return "<EnterpriseCustomerReportingConfiguration for Enterprise {enterprise_name}>".format(
            enterprise_name=self.enterprise_customer.name
        )

    def __repr__(self):
        """
        Return uniquely identifying string representation.
        """
        return self.__str__()

    def clean(self):
        """
        Override of clean method to perform additional validation on frequency and day_of_month/day_of week.
        """
        validation_errors = {}

        # Check that the frequency selections make sense.
        if self.frequency == self.FREQUENCY_TYPE_DAILY:
            self.day_of_month = None
            self.day_of_week = None
        elif self.frequency == self.FREQUENCY_TYPE_WEEKLY:
            if self.day_of_week is None or self.day_of_week == '':
                validation_errors['day_of_week'] = _('Day of week must be set if the frequency is weekly.')
            self.day_of_month = None
        elif self.frequency == self.FREQUENCY_TYPE_MONTHLY:
            if not self.day_of_month:
                validation_errors['day_of_month'] = _('Day of month must be set if the frequency is monthly.')
            self.day_of_week = None
        else:
            validation_errors[NON_FIELD_ERRORS] = _('Frequency must be set to either daily, weekly, or monthly.')

        # Check that fields related to the delivery method make sense.
        if self.delivery_method == self.DELIVERY_METHOD_EMAIL:
            if not self.email:
                validation_errors['email'] = _(
                    'Email(s) must be set if the delivery method is email.'
                )
            if not self.decrypted_password:
                validation_errors['decrypted_password'] = _(
                    'Decrypted password must be set if the delivery method is email.'
                )
        elif self.delivery_method == self.DELIVERY_METHOD_SFTP:
            if not self.sftp_hostname:
                validation_errors['sftp_hostname'] = _('SFTP Hostname must be set if the delivery method is sftp.')
            if not self.sftp_username:
                validation_errors['sftp_username'] = _('SFTP username must be set if the delivery method is sftp.')
            if not self.sftp_file_path:
                validation_errors['sftp_file_path'] = _('SFTP File Path must be set if the delivery method is sftp.')
            if not self.decrypted_sftp_password:
                validation_errors['decrypted_sftp_password'] = _(
                    'Decrypted SFTP password must be set if the delivery method is SFTP.'
                )

        if validation_errors:
            raise ValidationError(validation_errors)


class EnterpriseRoleAssignmentContextMixin:
    """
    Mixin for RoleAssignment models related to enterprises.
    """

    @property
    def enterprise_customer_uuids(self):
        """Get the enterprise customer uuids linked to the user."""
        enterprise_users = EnterpriseCustomerUser.objects.filter(user_id=self.user.id)
        if not enterprise_users:
            LOGGER.warning(
                'User {} has a {} of "{}" but is not linked to an enterprise. (ID: {})'.format(
                    self.user.id,
                    self.__class__,
                    self.role.name,
                    self.id
                ))
            return None

        return [str(enterprise_user.enterprise_customer.uuid) for enterprise_user in enterprise_users]

    def get_context(self):
        """
        Return the context for this role assignment class. A list is returned in case of user with multiple contexts.
        """
        return self.enterprise_customer_uuids


@python_2_unicode_compatible
class SystemWideEnterpriseRole(UserRole):
    """
    System wide user role definitions specific to Enterprise.

    .. no_pii:
    """

    def __str__(self):
        """
        Return human-readable string representation.
        """
        return "<SystemWideEnterpriseRole {role}>".format(role=self.name)

    def __repr__(self):
        """
        Return uniquely identifying string representation.
        """
        return self.__str__()


@python_2_unicode_compatible
class SystemWideEnterpriseUserRoleAssignment(EnterpriseRoleAssignmentContextMixin, UserRoleAssignment):
    """
    Model to map users to a SystemWideEnterpriseRole.

    .. no_pii:
    """

    role_class = SystemWideEnterpriseRole

    enterprise_customer = models.ForeignKey(
        EnterpriseCustomer,
        null=True,
        blank=True,
        related_name="system_wide_role_assignments",
        on_delete=models.CASCADE,
        help_text=_(
            'The EnterpriseCustomer for which the role is assigned for the user.  If creating a new assignment, '
            'you must first provide a user email and role, then click "Save and continue editing" '
            'BEFORE selecting from this dropdown.'
        ),
    )

    def has_access_to_all_contexts(self):
        """
        Returns true if the role for this assignment is ``ENTERPRISE_OPERATOR_ROLE``,
        or if ``applies_to_all_contexts`` is true; returns false otherwise.
        """
        return (self.role.name == ENTERPRISE_OPERATOR_ROLE) or self.applies_to_all_contexts  # pylint: disable=no-member

    def get_context(self):
        """
        Return the context for this role assignment class.
        """
        if self.has_access_to_all_contexts():
            return [ALL_ACCESS_CONTEXT]

        if self.enterprise_customer:
            return [str(self.enterprise_customer.uuid)]

        return super().get_context()

    def __str__(self):
        """
        Return human-readable string representation.
        """
        return "<SystemWideEnterpriseUserRoleAssignment for User {user} assigned to role {role}>".format(
            user=self.user.id,
            role=self.role.name  # pylint: disable=no-member
        )

    def __repr__(self):
        """
        Return uniquely identifying string representation.
        """
        return self.__str__()


@python_2_unicode_compatible
class EnterpriseFeatureRole(UserRole):
    """
    Enterprise-specific feature role definitions.

    .. no_pii:
    """

    def __str__(self):
        """
        Return human-readable string representation.
        """
        return "<EnterpriseFeatureRole {role}>".format(role=self.name)

    def __repr__(self):
        """
        Return uniquely identifying string representation.
        """
        return self.__str__()


@python_2_unicode_compatible
class EnterpriseFeatureUserRoleAssignment(EnterpriseRoleAssignmentContextMixin, UserRoleAssignment):
    """
    Model to map users to an EnterpriseFeatureRole.

    .. no_pii:
    """

    role_class = EnterpriseFeatureRole

    def __str__(self):
        """
        Return human-readable string representation.
        """
        return "<EnterpriseFeatureUserRoleAssignment for User {user} assigned to role {role}>".format(
            user=self.user.id,
            role=self.role.name  # pylint: disable=no-member
        )

    def __repr__(self):
        """
        Return uniquely identifying string representation.
        """
        return self.__str__()


class PendingEnterpriseCustomerAdminUser(TimeStampedModel):
    """
    Model for pending enterprise admin users.

    .. pii: The user_email field contains PII, but locally deleted via
    enterprise.signals.assign_or_delete_enterprise_admin_role when the
    admin registers a new account.
    .. pii_types: email_address
    .. pii_retirement: local_api, consumer_api
    """

    enterprise_customer = models.ForeignKey(
        EnterpriseCustomer,
        blank=False,
        null=False,
        on_delete=models.CASCADE,
    )
    user_email = models.EmailField(null=False, blank=False)
    history = HistoricalRecords()

    class Meta:
        app_label = 'enterprise'
        ordering = ['created']
        constraints = [
            models.UniqueConstraint(
                fields=['user_email', 'enterprise_customer'],
                name='unique pending admin user and EnterpriseCustomer',
            ),
        ]
        indexes = [
            models.Index(fields=['user_email', 'enterprise_customer']),
            models.Index(fields=['user_email']),
        ]

    @cached_property
    def admin_registration_url(self):
        """
        Returns a URL to be used by a pending enterprise admin user to register their account.
        """
        registration_url = '{}/{}/admin/register'.format(
            settings.ENTERPRISE_ADMIN_PORTAL_BASE_URL,
            self.enterprise_customer.slug
        )
        return registration_url

    @classmethod
    def activate_admin_permissions(cls, enterprise_customer_user):
        """
        Activates admin permissions for an existing PendingEnterpriseCustomerAdminUser.

        Specifically, the "enterprise_admin" system-wide role is assigned to the user and
        the PendingEnterpriseCustomerAdminUser record is removed.

        Requires an EnterpriseCustomerUser record to exist which ensures the user already
        has the "enterprise_learner" role as a prerequisite.

        Arguments:
            enterprise_customer_user: an EnterpriseCustomerUser instance
        """
        try:
            pending_admin_user = PendingEnterpriseCustomerAdminUser.objects.get(
                user_email=enterprise_customer_user.user.email,
                enterprise_customer=enterprise_customer_user.enterprise_customer,
            )
        except PendingEnterpriseCustomerAdminUser.DoesNotExist:
            return  # this is ok, nothing to do

        # get_or_create "enterprise_admin" role
        enterprise_admin_role, __ = SystemWideEnterpriseRole.objects.get_or_create(name=ENTERPRISE_ADMIN_ROLE)

        if not enterprise_customer_user.linked:
            # EnterpriseCustomerUser is no longer linked, so delete the "enterprise_admin" role and
            # their Tableau user.
            try:
                SystemWideEnterpriseUserRoleAssignment.objects.get(
                    user=enterprise_customer_user.user,
                    role=enterprise_admin_role,
                ).delete()
            except SystemWideEnterpriseUserRoleAssignment.DoesNotExist:
                pass

            delete_tableau_user(enterprise_customer_user)
            return  # nothing left to do

        # grant the "enterprise_admin" role
        SystemWideEnterpriseUserRoleAssignment.objects.get_or_create(
            user=enterprise_customer_user.user,
            role=enterprise_admin_role,
        )

        # Also create the Enterprise admin user in third-party analytics application with the enterprise
        # customer uuid as username.
        tableau_username = str(enterprise_customer_user.enterprise_customer.uuid).replace('-', '')
        create_tableau_user(tableau_username, enterprise_customer_user)

        # delete the PendingEnterpriseCustomerAdminUser record
        pending_admin_user.delete()

    def __str__(self):
        """
        Return human-readable string representation.
        """
        return "<PendingEnterpriseCustomerAdminUser {id}>: {enterprise_name} - {user_email}".format(
            id=self.id,
            enterprise_name=self.enterprise_customer.name,
            user_email=self.user_email,
        )

    def __repr__(self):
        """
        Return uniquely identifying string representation.
        """
        return self.__str__()


class EnterpriseAnalyticsUser(TimeStampedModel):
    """
    Model for analytics users.

     .. no_pii:
    """
    enterprise_customer_user = models.ForeignKey(
        EnterpriseCustomerUser,
        blank=False,
        null=False,
        on_delete=models.CASCADE
    )
    analytics_user_id = models.CharField(
        max_length=255,
        blank=False,
        null=False,
        help_text=_("User id in the third party analytics system."))
    history = HistoricalRecords()

    class Meta:
        app_label = 'enterprise'
        ordering = ['created']
        unique_together = (('enterprise_customer_user', 'analytics_user_id'),)

    def __str__(self):
        """
        Return human-readable string representation.
        """
        return "<EnterpriseAnalyticsUser {id}>: {enterprise_customer_user} - {analytics_user_id}".format(
            id=self.id,
            enterprise_customer_user=self.enterprise_customer_user.id,
            analytics_user_id=self.analytics_user_id,
        )

    def __repr__(self):
        """
        Return uniquely identifying string representation.
        """
        return self.__str__()
