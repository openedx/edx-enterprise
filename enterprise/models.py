# -*- coding: utf-8 -*-
"""
Database models for enterprise.
"""
from __future__ import absolute_import, unicode_literals

import collections
import os
from logging import getLogger
from uuid import uuid4

import six
from jsonfield.fields import JSONField
from simple_history.models import HistoricalRecords

from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.files.storage import default_storage
from django.core.urlresolvers import reverse
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.template import Context, Template
from django.utils.crypto import get_random_string
from django.utils.encoding import python_2_unicode_compatible
from django.utils.functional import lazy
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _

from model_utils.models import TimeStampedModel

from enterprise import utils
from enterprise.api_client.discovery import CourseCatalogApiServiceClient
from enterprise.api_client.lms import EnrollmentApiClient, ThirdPartyAuthApiClient, enroll_user_in_course_locally
from enterprise.constants import json_serialized_course_modes
from enterprise.utils import get_configuration_value
from enterprise.validators import validate_image_extension, validate_image_size
from six.moves.urllib.parse import urljoin  # pylint: disable=import-error,ungrouped-imports

LOGGER = getLogger(__name__)

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
        return super(EnterpriseCustomerManager, self).get_queryset().filter(active=True)


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
    """

    class Meta:
        app_label = 'enterprise'
        verbose_name = _("Enterprise Customer")
        verbose_name_plural = _("Enterprise Customers")

    objects = models.Manager()
    active_customers = EnterpriseCustomerManager()

    uuid = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    name = models.CharField(max_length=255, blank=False, null=False, help_text=_("Enterprise Customer name."))
    catalog = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=_("Course catalog for the Enterprise Customer.")
    )
    active = models.BooleanField(default=True)
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

    @property
    def identity_provider(self):
        """
        Return the unique slug for the identity provider associated with this enterprise customer.

        Returns `None` if enterprise customer does not have any identity provider.
        """
        try:
            return self.enterprise_customer_identity_provider and self.enterprise_customer_identity_provider.provider_id
        except ObjectDoesNotExist:
            return None

    def __str__(self):
        """
        Return human-readable string representation.
        """
        return "<EnterpriseCustomer {code}: {name}>".format(code=self.uuid, name=self.name)

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
                'enterprise_course_enrollment_page',
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
        Determine if the specified course run is contained in at least one of the enterprise's catalogs.

        Arguments:
            course_run_id (str): The string ID of the course or course run in question

        Returns:
            bool: Whether the enterprise catalog includes the given course run.
        """
        if self.catalog:
            client = CourseCatalogApiServiceClient(self.site)
            if client.is_course_in_catalog(self.catalog, course_run_id):
                return True

        for catalog in self.enterprise_customer_catalogs.all():
            if catalog.contains_content_items('key', [course_run_id]):
                return True

        return False


class EnterpriseCustomerUserManager(models.Manager):
    """
    Model manager for :class:`.EnterpriseCustomerUser` entity.

    This class should contain methods that create, modify or query :class:`.EnterpriseCustomerUser` entities.
    """

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
            return PendingEnterpriseCustomerUser.objects.get(user_email=user_email)
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
            link_record.delete()
        except User.DoesNotExist:
            # not capturing DoesNotExist intentionally to signal to view that link does not exist
            pending_link = PendingEnterpriseCustomerUser.objects.get(
                enterprise_customer=enterprise_customer, user_email=user_email
            )
            pending_link.delete()


@python_2_unicode_compatible
class EnterpriseCustomerUser(TimeStampedModel):
    """
    Model that keeps track of user - enterprise customer affinity.

    Fields:
        enterprise_customer (ForeignKey[:class:`.EnterpriseCustomer`]): enterprise customer
        user_id (:class:`django.db.models.IntegerField`): user identifier

    """

    enterprise_customer = models.ForeignKey(
        EnterpriseCustomer,
        blank=False,
        null=False,
        related_name='enterprise_customer_users',
        on_delete=models.deletion.CASCADE
    )
    user_id = models.PositiveIntegerField(null=False, blank=False)

    objects = EnterpriseCustomerUserManager()

    class Meta(object):
        app_label = 'enterprise'
        verbose_name = _("Enterprise Customer Learner")
        verbose_name_plural = _("Enterprise Customer Learners")
        unique_together = (("enterprise_customer", "user_id"),)

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
    def entitlements(self):
        """
        Return entitlement ids available to the learner along-with consent data.

        Returns an empty list if enterprise customer requires data sharing consent and learner does not agree.

        Returns:
            (list): A list of entitlements that learner can avail. Each item in the list is a dict with two
                key-value pairs,
                {
                    "requires_consent": True ,
                    "entitlement_id": 1
                }
                "requires_consent": True if learner must consent to data
                    sharing in order to get benefits of entitlement.
                "entitlement_id: id of the entitlements available to the learner.

        """
        # Check if Enterprise Learner consents to data sharing and store the boolean result
        DataSharingConsent = apps.get_model('consent', 'DataSharingConsent')  # pylint: disable=invalid-name
        learner_consent_enabled = DataSharingConsent.objects.filter(
            enterprise_customer=self.enterprise_customer,
            username=self.username,
            granted=True,
        ).exists()

        entitlements = self.enterprise_customer.enterprise_customer_entitlements

        # If Enterprise Customer requires account course specific consent then we return all entitlements
        # including whether or not to acquire learner's consent.
        if self.enterprise_customer.enforces_data_sharing_consent(EnterpriseCustomer.AT_ENROLLMENT):
            return [
                {
                    "entitlement_id": entitlement.entitlement_id,
                    "requires_consent": not learner_consent_enabled,
                } for entitlement in entitlements.all()
            ]

        # for all other cases learner is eligible to all entitlements.
        return [
            {
                "entitlement_id": entitlement.entitlement_id,
                "requires_consent": False,
            } for entitlement in entitlements.all()
            ]

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
            client = ThirdPartyAuthApiClient()
            return client.get_remote_id(self.enterprise_customer.identity_provider, user.username)
        return None

    def enroll(self, course_run_id, mode):
        """
        Enroll a user into a course track, and register an enterprise course enrollment.
        """
        enrollment_api_client = EnrollmentApiClient()
        # Check to see if the user's already enrolled and we have an enterprise course enrollment to track it.
        enrolled_in_course = enrollment_api_client.is_enrolled(self.username, course_run_id)
        if not enrolled_in_course:
            # Directly enroll into the audit track.
            enrollment_api_client.enroll_user_in_course(self.username, course_run_id, mode)
            utils.track_event(self.user_id, 'edx.bi.user.enterprise.enrollment.course', {
                'category': 'enterprise',
                'label': course_run_id,
                'enterprise_customer_uuid': str(self.enterprise_customer.uuid),
                'enterprise_customer_name': self.enterprise_customer.name,
                'mode': mode,
            })
        EnterpriseCourseEnrollment.objects.get_or_create(
            enterprise_customer_user=self,
            course_id=course_run_id
        )


@python_2_unicode_compatible
class PendingEnterpriseCustomerUser(TimeStampedModel):
    """
    Model that stores "future members" of enterprise customer.

    Fields:
        enterprise_customer (ForeignKey[:class:`.EnterpriseCustomer`]): enterprise customer
        user_email (:class:`django.db.models.EmailField`): user email

    """

    enterprise_customer = models.ForeignKey(EnterpriseCustomer, blank=False, null=False)
    user_email = models.EmailField(null=False, blank=False, unique=True)

    class Meta(object):
        app_label = 'enterprise'

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
class PendingEnrollment(TimeStampedModel):
    """
    Track future enrollments for PendingEnterpriseCustomerUser.

    Store a course ID, an intended enrollment mode, and a link to a PendingEnterpriseCustomerUser;
    when the PendingEnterpriseCustomerUser is converted to a full EnterpriseCustomerUser, API
    calls will be made to enroll the newly-created user in whatever courses have been added.
    """

    user = models.ForeignKey(
        PendingEnterpriseCustomerUser,
        null=False,
        on_delete=models.deletion.CASCADE
    )
    course_id = models.CharField(
        max_length=255,
        blank=False,
    )
    course_mode = models.CharField(
        max_length=25,
        blank=False
    )

    class Meta(object):
        app_label = 'enterprise'
        unique_together = (("user", "course_id"),)

    def complete_enrollment(self):
        """
        Enroll the linked user in the linked course.
        """
        user = User.objects.get(email=self.user.user_email)
        course_id = self.course_id
        course_mode = self.course_mode
        enroll_user_in_course_locally(user, course_id, course_mode)

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

    class Meta:
        """Meta class for this Django model."""

        app_label = 'enterprise'
        verbose_name = _("Branding Configuration")
        verbose_name_plural = _("Branding Configurations")

    def save(self, *args, **kwargs):  # pylint: disable=arguments-differ
        """Save the enterprise customer branding config."""
        if self.pk is None:
            logo_image = self.logo
            self.logo = None
            super(EnterpriseCustomerBrandingConfiguration, self).save(*args, **kwargs)
            self.logo = logo_image

        super(EnterpriseCustomerBrandingConfiguration, self).save(*args, **kwargs)

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


@python_2_unicode_compatible
class EnterpriseCustomerIdentityProvider(TimeStampedModel):
    """
    EnterpriseCustomerIdentityProvider is a One to One relationship between Enterprise Customer and Identity Provider.

    There should be a link between an enterprise customer and its Identity Provider. This relationship has
    following constraints
        1. An enterprise customer may or may not have an identity provider.
        2. An enterprise customer can not have more than one identity providers.
        3. Enterprise customer site should match with identity provider's site. (i.e. same domain names)

    Fields:
        enterprise_customer (ForeignKey[EnterpriseCustomer]): enterprise customer
        provider_id (:class:`django.db.models.SlugField`): The provider_id string of the identity provider.

    """

    enterprise_customer = models.OneToOneField(
        EnterpriseCustomer,
        blank=False,
        null=False,
        related_name="enterprise_customer_identity_provider"
    )
    provider_id = models.SlugField(
        null=False,
        blank=False,
        unique=True,
        help_text="Slug field containing a unique identifier for the identity provider.",
    )

    class Meta(object):
        app_label = 'enterprise'

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
    def provider_name(self):
        """
        Readable name for the identity provider.
        """
        identity_provider = utils.get_identity_provider(self.provider_id)
        return identity_provider and identity_provider.name


@python_2_unicode_compatible
class EnterpriseCustomerEntitlement(TimeStampedModel):
    """
    Enterprise Customer Entitlement is a relationship between and Enterprise customer and its entitlements.

    Users associated with an Enterprise Customer could be eligible for these entitlements resulting in partial or full
    discounts while taking paid courses on the edX platform.
    """

    class Meta(object):
        app_label = 'enterprise'
        verbose_name = _("Enterprise Customer Entitlement")
        verbose_name_plural = _("Enterprise Customer Entitlements")

    enterprise_customer = models.ForeignKey(EnterpriseCustomer, related_name="enterprise_customer_entitlements")
    entitlement_id = models.PositiveIntegerField(
        blank=False,
        null=False,
        unique=True,
        help_text=_("Enterprise customer's entitlement id for relationship with e-commerce coupon.")
    )
    history = HistoricalRecords()

    def __str__(self):
        """
        Return human-readable string representation.
        """
        return "<EnterpriseCustomerEntitlement {customer}: {id}>".format(
            customer=self.enterprise_customer,
            id=self.entitlement_id
        )

    def __repr__(self):
        """
        Return uniquely identifying string representation.
        """
        return self.__str__()


@python_2_unicode_compatible
class EnterpriseCourseEnrollment(TimeStampedModel):
    """
    Store information about the enrollment of a user in a course.

    This model is the central source of truth for information about
    whether a particular user, linked to a particular EnterpriseCustomer,
    has been enrolled in a course, and is the repository for any other
    relevant metadata about such an enrollment.
    """

    class Meta(object):
        unique_together = (('enterprise_customer_user', 'course_id',),)
        app_label = 'enterprise'

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
    history = HistoricalRecords()

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


@python_2_unicode_compatible
class EnterpriseCustomerCatalog(TimeStampedModel):
    """
    Store catalog information from course discovery specifically for Enterprises.

    We use this model to consolidate course catalog information, which includes
    information about catalogs, courses, programs, and possibly more in the
    future, as the course discovery service evolves.
    """

    uuid = models.UUIDField(
        primary_key=True,
        default=uuid4,
        editable=False
    )
    title = models.CharField(
        default='All Content',
        max_length=20,
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
    content_filter = JSONField(
        default={},
        blank=True,
        null=True,
        load_kwargs={'object_pairs_hook': collections.OrderedDict},
        help_text=_(
            "Query parameters which will be used to filter the discovery service's search/all endpoint results, "
            "specified as a Json object. An empty Json object means that all available content items will be "
            "included in the catalog."
        )
    )
    enabled_course_modes = JSONField(
        default=json_serialized_course_modes,
        help_text=_('Ordered list of enrollment modes which can be displayed to learners for course runs in'
                    ' this catalog.'),
    )

    history = HistoricalRecords()

    class Meta(object):
        verbose_name = _("Enterprise Customer Catalog")
        verbose_name_plural = _("Enterprise Customer Catalogs")
        app_label = 'enterprise'

    def __str__(self):
        """
        Return human-readable string representation.
        """
        return (
            "<EnterpriseCustomerCatalog with uuid '{uuid}' "
            "for EnterpriseCustomer {enterprise_customer_name}>".format(
                uuid=self.uuid,
                enterprise_customer_name=self.enterprise_customer.name
            )
        )

    def __repr__(self):
        """
        Return uniquely identifying string representation.
        """
        return self.__str__()

    def get_paginated_content(self, query_parameters):
        """
        Return paginated discovery service search results.

        Arguments:
            query_parameters (dict): Additional query parameters to add to the search API call, e.g. page.
        Returns:
            dict: The paginated discovery service search results.
        """
        results = []
        query = self.content_filter.copy()
        query.update(query_parameters)
        catalog_client = CourseCatalogApiServiceClient(self.enterprise_customer.site)
        search_results = catalog_client.get_search_results(query, traverse_pagination=False)
        for content in search_results['results']:
            if content['content_type'] == 'courserun' and content['has_enrollable_seats']:
                results.append(content)
            elif content['content_type'] == 'program' and content['is_program_eligible_for_one_click_purchase']:
                results.append(content)

        response = {
            'count': len(results),
            'next': search_results['next'],
            'previous': search_results['previous'],
            'results': results,
            }

        return response

    def contains_content_items(self, content_id_field_name, content_id_values):
        """
        Return True if this catalog contains the items identified by `content_id_field_name` and `content_id_values`.

        Arguments:
            content_id_field_name (str): The name of the field on the catalog content item
                                         that stores the item's unique identifier, e.g. "key", "uuid".
            content_id_values (list): The unique identifiers of the catalog content items.

        Returns:
            bool: True if this catalog contains the given content items, else false.
        """
        # Check the content_filter defined for this catalog to see if the
        # unique key is a part of the filter that defines this catalog.
        content_ids_in_catalog = set(self.content_filter.get(content_id_field_name, []))
        if not content_ids_in_catalog:
            # Otherwise add the unique key values to the content_filter and query
            # the discovery service for the existence of the content.
            updated_content_filter = self.content_filter.copy()
            updated_content_filter[content_id_field_name] = content_id_values
            results = CourseCatalogApiServiceClient().get_search_results(updated_content_filter)
            if results:
                for content in results:
                    if content['content_type'] == 'courserun' and content['has_enrollable_seats']:
                        content_ids_in_catalog.add(content[content_id_field_name])
                    elif content['content_type'] == 'program' and content['is_program_eligible_for_one_click_purchase']:
                        content_ids_in_catalog.add(content[content_id_field_name])

        # Diff the content IDs found in the catalog with the set of
        # IDs which we are checking for existence.
        intersection = set(content_id_values) & content_ids_in_catalog
        return len(intersection) == len(content_id_values)

    def get_course_run(self, course_run_id):
        """
        Get all of the metadata for the given course run.

        Arguments:
            course_run_id (str): The course run key which identifies the course run.

        Return:
            dict: The course run metadata.
        """
        if not self.contains_content_items('key', [course_run_id]):
            return None
        return CourseCatalogApiServiceClient(self.enterprise_customer.site).get_course_run(course_run_id)

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
        if not self.contains_content_items('key', [course_run_id]):
            return None, None

        return CourseCatalogApiServiceClient(self.enterprise_customer.site).get_course_and_course_run(course_run_id)

    def get_program(self, program_uuid):
        """
        Get all of the metadata for the given program.

        Arguments:
            program_uuid (str): The program UUID which identifies the program.

        Return:
            dict: The program metadata.
        """
        if not self.contains_content_items('uuid', [program_uuid]):
            return None
        return CourseCatalogApiServiceClient(self.enterprise_customer.site).get_program_by_uuid(program_uuid)

    def get_course_run_enrollment_url(self, course_run_key):
        """
        Return enterprise course enrollment page url with the catalog information for the given course.

        Arguments:
            course_run_key (str): The course run id for the course to be displayed.

        Returns:
            (str): Enterprise landing page url.
        """
        url = self.enterprise_customer.get_course_run_enrollment_url(course_run_key)
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
        return utils.update_query_parameters(url, {'catalog': self.uuid})


@python_2_unicode_compatible
class EnrollmentNotificationEmailTemplate(TimeStampedModel):
    """
    Store optional templates to use when emailing users about course enrollment events.
    """

    class Meta(object):
        app_label = 'enterprise'

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
    # We are adding this field preemptively as we plan to support FTP, but don't have the details yet.
    DELIVERY_METHOD_FTP = 'ftp'

    DELIVERY_METHOD_CHOICES = (
        (DELIVERY_METHOD_EMAIL, DELIVERY_METHOD_EMAIL),
        (DELIVERY_METHOD_FTP, DELIVERY_METHOD_FTP),
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

    enterprise_customer = models.OneToOneField(
        EnterpriseCustomer, blank=False, null=False, verbose_name=_("Enterprise Customer")
    )
    active = models.BooleanField(blank=False, null=False, verbose_name=_("Active"))
    delivery_method = models.CharField(
        max_length=20,
        choices=DELIVERY_METHOD_CHOICES,
        blank=False,
        default=DELIVERY_METHOD_EMAIL,
        verbose_name=_("Delivery Method"),
        help_text=_("The method in which the data should be sent.")
    )
    email = models.EmailField(blank=False, null=False, verbose_name=_("Email"))
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
    initialization_vector = models.BinaryField(
        max_length=32,
        blank=False,
        null=False,
        editable=False,
        verbose_name=_("Password Encryption Initialization Vector"),
        help_text=_("This is the initialization vector used to encrypt the password using AESencr")
    )
    password = models.BinaryField(
        max_length=256,
        blank=False,
        null=False,
        editable=False,
        verbose_name=_("Password"),
    )

    class Meta:
        app_label = 'enterprise'

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

    def save(self, *args, **kwargs):  # pylint: disable=arguments-differ
        """
        Override of model save method to dynamically generate the password field and perform additional validation.
        """
        self.initialization_vector = utils.generate_aes_initialization_vector()
        self.password = utils.encrypt_string(
            get_random_string(length=32),
            self.initialization_vector
        )
        self.full_clean()
        super(EnterpriseCustomerReportingConfiguration, self).save(*args, **kwargs)

    def clean(self):
        """
        Override of clean method to perform additional validation on frequency and day_of_month/day_of week.
        """
        if self.frequency == self.FREQUENCY_TYPE_DAILY:
            self.day_of_month = None
            self.day_of_week = None
        elif self.frequency == self.FREQUENCY_TYPE_WEEKLY:
            if self.day_of_week is None or self.day_of_week == '':
                raise ValidationError({'day_of_week': _('Day of week must be set if the frequency is weekly.')})
            self.day_of_month = None
        elif self.frequency == self.FREQUENCY_TYPE_MONTHLY:
            if not self.day_of_month:
                raise ValidationError({'day_of_month': _('Day of month must be set if the frequency is monthly.')})
            self.day_of_week = None
        else:
            raise ValidationError(_('Frequency must be set to either daily, weekly, or monthly.'))
