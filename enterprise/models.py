# -*- coding: utf-8 -*-
"""
Database models for enterprise.
"""
from __future__ import absolute_import, unicode_literals

import os
from logging import getLogger
from uuid import uuid4

import six
from simple_history.models import HistoricalRecords

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.core.exceptions import ObjectDoesNotExist
from django.core.files.storage import default_storage
from django.core.urlresolvers import reverse
from django.db import models
from django.template import Context, Template
from django.utils.encoding import python_2_unicode_compatible
from django.utils.functional import lazy
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _

from model_utils.models import TimeStampedModel

from enterprise import utils
from enterprise.lms_api import ThirdPartyAuthApiClient, enroll_user_in_course_locally
from enterprise.utils import NotConnectedToOpenEdX
from enterprise.validators import validate_image_extension, validate_image_size
from six.moves.urllib.parse import urljoin  # pylint: disable=import-error,ungrouped-imports

try:
    from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers
except ImportError:
    configuration_helpers = None

logger = getLogger(__name__)  # pylint: disable=invalid-name

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
    site = models.ForeignKey(Site, related_name="enterprise_customers")

    DATA_CONSENT_OPTIONAL = 'optional'
    AT_LOGIN = 'at_login'
    AT_ENROLLMENT = 'at_enrollment'
    EXTERNALLY_MANAGED = 'externally_managed'
    DATA_SHARING_CONSENT_CHOICES = (
        (DATA_CONSENT_OPTIONAL, 'Optional'),
        (AT_LOGIN, 'At Login'),
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
        default=DATA_CONSENT_OPTIONAL,
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

    require_account_level_consent = models.BooleanField(
        default=False,
        help_text=_(
            "Specifies whether every consent interaction should ask for account-wide consent, rather than only "
            "the specific scope at which the interaction is happening."
        )
    )

    @property
    def identity_provider(self):
        """
        Unique slug for the identity provider associated with this enterprise customer.

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
            argument can either be "optional", 'at_login' or 'at_enrollment'
        """
        return self.requests_data_sharing_consent and self.enforce_data_sharing_consent == enforcement_location

    @property
    def requests_data_sharing_consent(self):
        """
        Determine whether the enterprise customer has enabled the data sharing consent request.
        """
        return self.enable_data_sharing_consent and self.enforce_data_sharing_consent != self.EXTERNALLY_MANAGED

    def get_course_enrollment_url(self, course_run_key):
        """
        Return enterprise landing page url for the given course.

        Arguments:
            course_run_key (str): The course run id for the course to be displayed.
        Returns:
            (str): Enterprise landing page url.
        """
        if configuration_helpers is None:
            raise NotConnectedToOpenEdX(
                _("This package must be installed in an EdX environment to look up configuration.")
            )

        return urljoin(
            configuration_helpers.get_value('LMS_ROOT_URL', settings.LMS_ROOT_URL),
            reverse(
                'enterprise_course_enrollment_page',
                kwargs={'enterprise_uuid': self.uuid, 'course_id': course_run_key}
            )
        )


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
            self.create(enterprise_customer=enterprise_customer, user_id=existing_user.id)
        except User.DoesNotExist:
            PendingEnterpriseCustomerUser.objects.create(enterprise_customer=enterprise_customer, user_email=user_email)

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
        EnterpriseCustomer, blank=False, null=False, related_name='enterprise_customer_users'
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
        learner_consent_state = self.data_sharing_consent.first()
        learner_consent_enabled = learner_consent_state and learner_consent_state.enabled

        entitlements = self.enterprise_customer.enterprise_customer_entitlements

        # If Enterprise Customer requires account wide consent then we return either all or no entitlement
        # depending on learner's consent state
        if self.enterprise_customer.enforces_data_sharing_consent(EnterpriseCustomer.AT_LOGIN):
            return [
                {
                    "entitlement_id": entitlement.entitlement_id,
                    "requires_consent": not learner_consent_enabled,
                } for entitlement in entitlements.all() if learner_consent_enabled
            ]

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
        related_name="branding_configuration"
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

    def save(self, *args, **kwargs):
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
class UserDataSharingConsentAudit(TimeStampedModel):
    """
    Store consent information for an EnterpriseCustomerUser.

    Object that exists to store the canonical state of whether a particular
    user has given consent for their course data to be shared with a particular
    enterprise customer.
    """

    class Meta(object):
        app_label = 'enterprise'
        verbose_name = "Data Sharing Consent Audit State"
        verbose_name_plural = "Data Sharing Consent Audit States"

    NOT_SET = 'not_set'
    ENABLED = 'enabled'
    DISABLED = 'disabled'
    EXTERNALLY_MANAGED = 'external'
    STATE_CHOICES = (
        (NOT_SET, 'Not set'),
        (ENABLED, 'Enabled'),
        (DISABLED, 'Disabled'),
        (EXTERNALLY_MANAGED, 'Managed Externally'),
    )

    ENABLED_STATES = [
        ENABLED,
        EXTERNALLY_MANAGED,
    ]

    user = models.ForeignKey(EnterpriseCustomerUser, related_name='data_sharing_consent')

    state = models.CharField(
        max_length=8,
        blank=False,
        choices=STATE_CHOICES,
        default=NOT_SET,
        help_text=_(
            "Stores whether the learner linked to this model has consented to "
            "have their information shared with the linked EnterpriseCustomer."
        )
    )

    history = HistoricalRecords()

    @property
    def enabled(self):
        """
        Determine whether the user has enabled data sharing.
        """
        return self.state in self.ENABLED_STATES

    def __str__(self):
        """
        Return human-readable string representation.
        """
        return '<UserDataSharingConsentAudit for {} and {}: {}>'.format(
            self.user.user_email,
            self.user.enterprise_customer.name,
            self.state,
        )

    def __repr__(self):
        """
        Return uniquely identifying string representation.
        """
        return self.__str__()


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
        help_text=_(
            "The enterprise learner to which this enrollment is attached."
        )
    )
    consent_granted = models.NullBooleanField(
        help_text=_(
            "Whether the learner has granted consent for this particular course."
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

    def consent_available(self):
        """
        Determine whether we have consent to share details about this enrollment.

        If we have a definitive consent state stored on this enrollment directly
        (that is, if at enrollment the user explicitly chose to grant or deny consent
        at enrollment), then we'll use that value and not go any further. However, if
        the user did not do so, then we'll check to see if we have an account-wide
        consent state that we can use to make that determination.
        """
        if self.consent_granted is not None:
            # If the state isn't indeterminate, return immediately.
            return self.consent_granted
        else:
            # If it is indeterminate...

            # Check for an account-wide value and use that.
            consent_state = self.enterprise_customer_user.data_sharing_consent.first()
            if consent_state is not None:
                return consent_state.enabled
            else:
                # If there isn't an account-wide value, act as though we do not have consent.
                return False

    @property
    def consent_needed(self):
        """
        Determine if consent is necessary, but has not been provided yet.
        """
        if self.consent_available():
            return False
        else:
            enterprise_customer = self.enterprise_customer_user.enterprise_customer
            return any(
                [
                    enterprise_customer.enforces_data_sharing_consent(EnterpriseCustomer.AT_ENROLLMENT),
                    enterprise_customer.enforces_data_sharing_consent(EnterpriseCustomer.AT_LOGIN),
                ]
            )

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

    def save(self, *args, **kwargs):
        """
        When saving an EnterpriseCourseEnrollment, update the account-level consent if needed.
        """
        enterprise_customer = self.enterprise_customer_user.enterprise_customer

        if enterprise_customer.enforce_data_sharing_consent == EnterpriseCustomer.EXTERNALLY_MANAGED:
            # If the consent is externally managed, create a record indicating external consent.
            account_consent_equivalent = UserDataSharingConsentAudit.EXTERNALLY_MANAGED
        elif self.consent_granted:
            # If explicit consent has been provided, create a record indicating that.
            account_consent_equivalent = UserDataSharingConsentAudit.ENABLED
        elif self.consent_granted is not None:
            # If consent was declined, create a record indicating that.
            account_consent_equivalent = UserDataSharingConsentAudit.DISABLED
        else:
            # If no explicit consent state was set, indicate that.
            account_consent_equivalent = UserDataSharingConsentAudit.NOT_SET

        # This is an awful hack. Once we migrate to the planned generic consent architecture, it can DIAF.
        if enterprise_customer.require_account_level_consent:
            UserDataSharingConsentAudit.objects.update_or_create(
                user=self.enterprise_customer_user,
                defaults={'state': account_consent_equivalent}
            )

        super(EnterpriseCourseEnrollment, self).save(*args, **kwargs)


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
    site = models.OneToOneField(Site, related_name="enterprise_enrollment_template")
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
        return '<EnrollmentNotificationEmailTemplate for site with ID {}>'.format(
            self.site.id
        )

    def __repr__(self):
        """
        Return uniquely identifying string representation.
        """
        return self.__str__()
