# -*- coding: utf-8 -*-
"""
Models for edX Enterprise's Consent application.
"""

from __future__ import absolute_import, unicode_literals

from consent.mixins import ConsentModelMixin
from simple_history.models import HistoricalRecords

from django.core.exceptions import ValidationError
from django.db import IntegrityError, models
from django.utils.translation import ugettext_lazy as _

from model_utils.models import TimeStampedModel

from enterprise.models import EnterpriseCustomer


class DataSharingConsentQuerySet(models.query.QuerySet):
    """
    Customized QuerySets for the ``DataSharingConsent`` model.

    When searching for any ``DataSharingConsent`` object, if it doesn't exist, return a single
    ``ProxyDataSharingConsent`` object which behaves just like a ``DataSharingConsent`` object
    except is not saved in the database until committed.
    """

    def get(self, *args, **kwargs):
        """
        Perform the query and returns a single object matching the given keyword arguments.

        This customizes the queryset to return an instance of ``ProxyDataSharingConsent`` when
        the searched-for ``DataSharingConsent`` instance does not exist.
        """
        try:
            return super(DataSharingConsentQuerySet, self).get(*args, **kwargs)
        except DataSharingConsent.DoesNotExist:
            return ProxyDataSharingConsent(**kwargs)


class DataSharingConsentManager(models.Manager.from_queryset(DataSharingConsentQuerySet)):  # pylint: disable=no-member
    """
    Model manager for :class:`.DataSharingConsent` model.

    Uses a QuerySet that returns a ``ProxyDataSharingConsent`` object when the searched-for
    ``DataSharingConsent`` object does not exist. Otherwise behaves the same as a normal manager.
    """

    pass


class ProxyDataSharingConsent(ConsentModelMixin):
    """
    A proxy-model of the ``DataSharingConsent`` model; it's not a real model, but roughly behaves like one.

    Upon commit, a real ``DataSharingConsent`` object which mirrors the ``ProxyDataSharingConsent`` object's
    pseudo-model-fields is created, returned, and saved in the database. The remnant, in-heap
    ``ProxyDataSharingConsent`` object may be deleted afterwards, but if not, its ``exists`` fields remains ``True``
    to indicate that the object has been committed.

    NOTE: This class will be utilized when we implement program level consent by having an abstraction over these
          consent objects per course.
    """

    objects = DataSharingConsentManager()

    def __init__(self, enterprise_customer=None, username='', course_id='', granted=False):
        """
        Initialize a proxy version of ``DataSharingConsent`` which behaves similarly but does not exist in the DB.
        """
        self.enterprise_customer = enterprise_customer
        self.username = username
        self.course_id = course_id
        self.granted = granted
        self.exists = False

    def commit(self):
        """
        Commit a real ``DataSharingConsent`` object to the database, mirroring current field settings.

        :return: A ``DataSharingConsent`` object if validation is successful, otherwise ``None``.
        """
        try:
            consent = DataSharingConsent.objects.create(
                enterprise_customer=self.enterprise_customer,
                username=self.username,
                course_id=self.course_id,
                granted=self.granted
            )
            self.exists = consent.exists
            return consent
        except (ValidationError, IntegrityError):
            return None


class Consent(TimeStampedModel):
    """
    An abstract base model for representing any type of consent.
    """

    class Meta:
        """
        Meta class for the ``Consent`` model.
        """

        abstract = True
        app_label = 'consent'

    enterprise_customer = models.ForeignKey(
        EnterpriseCustomer,
        blank=False,
        null=False,
        related_name='enterprise_customer_consent',
        on_delete=models.deletion.CASCADE
    )
    username = models.CharField(
        max_length=255,
        blank=False,
        null=False,
        help_text=_("Name of the user whose consent state is stored.")
    )
    granted = models.NullBooleanField(help_text=_("Whether consent is granted."))

    @property
    def exists(self):
        """
        Return whether the instance exists or not.
        """
        return bool(self.pk)


class DataSharingConsent(ConsentModelMixin, Consent):  # pylint: disable=model-missing-unicode
    """
    An abstract representation of Data Sharing Consent granted to an Enterprise for a course by a User.

    The model is used to store a persistent, historical consent state for users granting, not granting, or revoking
    data sharing consent to an Enterprise for a course.
    """

    class Meta(Consent.Meta):
        """
        Meta class for the ``DataSharingConsent`` model.
        """

        abstract = False
        verbose_name = _("Data Sharing Consent Record")
        verbose_name_plural = _("Data Sharing Consent Records")
        unique_together = (("enterprise_customer", "username", "course_id"),)

    objects = DataSharingConsentManager()

    course_id = models.CharField(
        max_length=255,
        blank=False,
        help_text=_("Course key for which data sharing consent is granted.")
    )
    history = HistoricalRecords()
