# -*- coding: utf-8 -*-
"""
Models for edX Enterprise's Consent application.
"""

from __future__ import absolute_import, unicode_literals

from consent.errors import InvalidProxyConsent
from consent.mixins import ConsentModelMixin
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from simple_history.models import HistoricalRecords

from django.db import models
from django.utils.translation import ugettext_lazy as _

from model_utils.models import TimeStampedModel

from enterprise.models import EnterpriseCustomer
from enterprise.utils import parse_course_key


class DataSharingConsentQuerySet(models.query.QuerySet):
    """
    Customized QuerySets for the ``DataSharingConsent`` model.

    When searching for any ``DataSharingConsent`` object, if it doesn't exist, return a single
    ``ProxyDataSharingConsent`` object which behaves just like a ``DataSharingConsent`` object
    except is not saved in the database until committed.
    """

    def proxied_get(self, *args, **kwargs):
        """
        Perform the query and returns a single object matching the given keyword arguments.

        This customizes the queryset to return an instance of ``ProxyDataSharingConsent`` when
        the searched-for ``DataSharingConsent`` instance does not exist.
        """
        original_kwargs = kwargs.copy()
        if 'course_id' in kwargs:
            try:
                # Check if we have a course ID or a course run ID
                course_run_key = str(CourseKey.from_string(kwargs['course_id']))
            except InvalidKeyError:
                # The ID we have is for a course instead of a course run; fall through
                # to the second check.
                pass
            else:
                try:
                    # Try to get the record for the course run specifically
                    return self.get(*args, **kwargs)
                except DataSharingConsent.DoesNotExist:
                    # A record for the course run didn't exist, so modify the query
                    # parameters to look for just a course record on the second pass.
                    kwargs['course_id'] = parse_course_key(course_run_key)

        try:
            return self.get(*args, **kwargs)
        except DataSharingConsent.DoesNotExist:
            return ProxyDataSharingConsent(**original_kwargs)


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

    def __init__(
            self,
            enterprise_customer=None,
            username='',
            course_id='',
            program_uuid='',
            granted=False,
            exists=False,
            child_consents=None,
            **kwargs
    ):
        """
        Initialize a proxy version of ``DataSharingConsent`` which behaves similarly but does not exist in the DB.
        """
        ec_keys = {}
        for key in kwargs:
            if str(key).startswith('enterprise_customer__'):
                enterprise_customer_detail = key[len('enterprise_customer__'):]
                ec_keys[enterprise_customer_detail] = kwargs[key]

        if ec_keys:
            enterprise_customer = EnterpriseCustomer.objects.get(**ec_keys)  # pylint: disable=no-member

        self.enterprise_customer = enterprise_customer
        self.username = username
        self.course_id = course_id
        self.program_uuid = program_uuid
        self.granted = granted
        self._exists = exists
        self._child_consents = child_consents or []

    @classmethod
    def from_children(cls, program_uuid, *children):
        """
        Build a ProxyDataSharingConsent using the details of the received consent records.
        """
        if not children or any(child is None for child in children):
            return None
        granted = all((child.granted for child in children))
        exists = any((child.exists for child in children))
        usernames = set([child.username for child in children])
        enterprises = set([child.enterprise_customer for child in children])
        if not len(usernames) == len(enterprises) == 1:
            raise InvalidProxyConsent(
                'Children used to create a bulk proxy consent object must '
                'share a single common username and EnterpriseCustomer.'
            )
        username = children[0].username
        enterprise_customer = children[0].enterprise_customer
        return cls(
            enterprise_customer=enterprise_customer,
            username=username,
            program_uuid=program_uuid,
            exists=exists,
            granted=granted,
            child_consents=children
        )

    def commit(self):
        """
        Commit a real ``DataSharingConsent`` object to the database, mirroring current field settings.

        :return: A ``DataSharingConsent`` object if validation is successful, otherwise ``None``.
        """
        if self._child_consents:
            consents = []

            for consent in self._child_consents:
                consent.granted = self.granted
                consents.append(consent.save() or consent)

            return ProxyDataSharingConsent.from_children(self.program_uuid, *consents)

        consent, _ = DataSharingConsent.objects.update_or_create(
            enterprise_customer=self.enterprise_customer,
            username=self.username,
            course_id=self.course_id,
            defaults={
                'granted': self.granted
            }
        )
        self._exists = consent.exists
        return consent

    def save(self, *args, **kwargs):  # pylint: disable=unused-argument
        """
        Synonym function for ``commit``.
        """
        return self.commit()


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
    def _exists(self):
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
