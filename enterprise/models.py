# -*- coding: utf-8 -*-
"""
Database models for enterprise.
"""
from __future__ import absolute_import, unicode_literals

import os
from uuid import uuid4

from simple_history.models import HistoricalRecords  # likely a bug in import order checker

from django.contrib.sites.models import Site
from django.core.files.storage import default_storage
from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _

from model_utils.models import TimeStampedModel

from .validators import validate_image_extension, validate_image_size


class EnterpriseCustomerManager(models.Manager):
    """
    Model manager for Enterprise Customer model.

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
            `                                other parts of the system (SSO, ecommerce, analytics etc.)
        name (CharField): Enterprise Customer name
        active (BooleanField): used to mark inactive Enterprise Customers - implements "soft delete" pattern
    """

    class Meta(object):
        verbose_name = _("Enterprise Customer")
        verbose_name_plural = _("Enterprise Customers")

    objects = models.Manager()
    active_customers = EnterpriseCustomerManager()

    uuid = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    name = models.CharField(max_length=255, blank=False, null=False, help_text=_("Enterprise Customer name."))
    active = models.BooleanField(default=True)
    history = HistoricalRecords()

    site = models.ForeignKey(Site, related_name="enterprise_customers")

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


@python_2_unicode_compatible
class EnterpriseCustomerUser(TimeStampedModel):
    """
    Model that keeps track of user - enterprise customer affinity.

    Fields:
        enterprise_customer (ForeignKey[EnterpriseCustomer]): enterprise customer
        user_id (IntegerField): user identifier
    """

    enterprise_customer = models.ForeignKey(EnterpriseCustomer, blank=False, null=False)
    user_id = models.PositiveIntegerField(null=False, blank=False)

    class Meta(object):
        verbose_name = _("Enterprise Customer User")
        verbose_name_plural = _("Enterprise Customer Users")
        unique_together = (("enterprise_customer", "user_id"),)

    def __str__(self):
        """
        Return human-readable string representation.
        """
        return "<EnterpriseCustomerUser {ID}: {enterprise_name} - {user_id}>".format(
            ID=self.id,
            enterprise_name=self.enterprise_customer.name,
            user_id=self.user_id,
        )

    def __repr__(self):
        """
        Return uniquely identifying string representation.
        """
        return self.__str__()


def logo_path(instance, filename):
    """
    Delete the file if it already exist and returns the enterprise customer logo image path.

    :param instance: EnterpriseCustomerBrandingConfiguration object
    :param filename: file to upload
    :return path: path of image file e.g. enterprise/branding/<model.id>/<model_id>_logo.<ext>.lower()
    """
    extension = os.path.splitext(filename)[1].lower()
    instance_id = str(instance.id)
    fullname = os.path.join('enterprise/branding/', instance_id, instance_id + '_logo' + extension)
    if default_storage.exists(fullname):
        default_storage.delete(fullname)
    return fullname


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
        related_name='branding_configuration'
    )
    logo = models.ImageField(
        upload_to=logo_path,
        help_text=_(u'Please add only .PNG files for logo images.'),
        null=True, blank=True, max_length=255,
        validators=[validate_image_extension, validate_image_size]
    )

    class Meta:
        """Meta class for this Django model."""

        verbose_name = _('Branding Configuration')
        verbose_name_plural = _('Branding Configurations')

    def save(self, *args, **kwargs):
        """Save the enterprise customer branding config."""
        if self.pk is None:
            logo_image = self.logo
            self.logo = None
            super(EnterpriseCustomerBrandingConfiguration, self).save(*args, **kwargs)
            self.logo = logo_image

        super(EnterpriseCustomerBrandingConfiguration, self).save(*args, **kwargs)
