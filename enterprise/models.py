# -*- coding: utf-8 -*-
"""
Database models for enterprise.
"""
from __future__ import absolute_import, unicode_literals

import os
from logging import getLogger
from uuid import uuid4

from simple_history.models import HistoricalRecords

from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.core.exceptions import ObjectDoesNotExist
from django.core.files.storage import default_storage
from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _

from model_utils.models import TimeStampedModel

from enterprise import utils
from enterprise.validators import validate_image_extension, validate_image_size

logger = getLogger(__name__)  # pylint: disable=invalid-name


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
        verbose_name = _("Enterprise Customer")
        verbose_name_plural = _("Enterprise Customers")

    objects = models.Manager()
    active_customers = EnterpriseCustomerManager()

    uuid = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    name = models.CharField(max_length=255, blank=False, null=False, help_text=_("Enterprise Customer name."))
    catalog = models.PositiveIntegerField(null=True, help_text=_("Course catalog for the Enterprise Customer."))
    active = models.BooleanField(default=True)
    history = HistoricalRecords()
    site = models.ForeignKey(Site, related_name="enterprise_customers")

    DATA_CONSENT_OPTIONAL = 'optional'
    AT_LOGIN = 'at_login'
    AT_ENROLLMENT = 'at_enrollment'
    DATA_SHARING_CONSENT_CHOICES = (
        (DATA_CONSENT_OPTIONAL, 'Optional'),
        (AT_LOGIN, 'At Login'),
        (AT_ENROLLMENT, 'At Enrollment'),
    )

    enable_data_sharing_consent = models.BooleanField(
        default=False,
        help_text=_(
            "This field is used to determine whether data sharing consent is enabled or "
            "disabled for users signing in using this enterprise customer. If disabled, consent "
            "will not be requested, and eligible data will not be shared."
        )
    )

    enforce_data_sharing_consent = models.CharField(
        max_length=25,
        blank=False,
        choices=DATA_SHARING_CONSENT_CHOICES,
        default=DATA_CONSENT_OPTIONAL,
        help_text=_(
            "This field determines if data sharing consent is optional, if it's required at login, "
            "or if it's required when registering for eligible courses."
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
        return self.enable_data_sharing_consent


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

    enterprise_customer = models.ForeignKey(EnterpriseCustomer, blank=False, null=False)
    user_id = models.PositiveIntegerField(null=False, blank=False)

    objects = EnterpriseCustomerUserManager()

    class Meta(object):
        verbose_name = _("Enterprise Customer User")
        verbose_name_plural = _("Enterprise Customer Users")
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
        help_text=_(u"Please add only .PNG files for logo images."),
        null=True, blank=True, max_length=255,
        validators=[validate_image_extension, validate_image_size]
    )

    class Meta:
        """Meta class for this Django model."""

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
    STATE_CHOICES = (
        (NOT_SET, 'Not set'),
        (ENABLED, 'Enabled'),
        (DISABLED, 'Disabled'),
    )

    user = models.ForeignKey(EnterpriseCustomerUser)

    state = models.CharField(
        max_length=8,
        blank=False,
        choices=STATE_CHOICES,
        default=NOT_SET,
        help_text=_(
            "Stores whether the user linked to this model has consented to have "
            "their information shared with the linked EnterpriseCustomer."
        )
    )

    history = HistoricalRecords()

    @property
    def enabled(self):
        """
        Determine whether the user has enabled data sharing.
        """
        return self.state == self.ENABLED

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
