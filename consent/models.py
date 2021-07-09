# -*- coding: utf-8 -*-
"""
Models for edX Enterprise's Consent application.
"""

import logging

import six
from simple_history.models import HistoricalRecords

from django.core.exceptions import ImproperlyConfigured
from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from django.utils.functional import lazy
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _

from model_utils.models import TimeStampedModel

from consent.errors import InvalidProxyConsent
from consent.mixins import ConsentModelMixin
from enterprise.api_client.discovery import get_course_catalog_api_service_client
from enterprise.models import EnterpriseCustomer

mark_safe_lazy = lazy(mark_safe, six.text_type)  # pylint: disable=invalid-name
LOGGER = logging.getLogger(__name__)


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
                # Try to get the record for the course OR course run, depending on what we got in kwargs,
                # course_id or course_run_id
                return self.get(*args, **kwargs)
            except DataSharingConsent.DoesNotExist:
                # If here, either the record for course OR course run doesn't exist.
                # Try one more time by modifying the query parameters to look for just a course record this time.
                site = None
                if 'enterprise_customer' in kwargs:
                    site = kwargs['enterprise_customer'].site

                try:
                    course_id = get_course_catalog_api_service_client(site=site).get_course_id(
                        course_identifier=kwargs['course_id']
                    )
                    kwargs['course_id'] = course_id
                except ImproperlyConfigured:
                    LOGGER.warning('CourseCatalogApiServiceClient is improperly configured.')

        try:
            # Try to get the record of course
            return self.get(*args, **kwargs)
        except DataSharingConsent.DoesNotExist:
            # If here, the record doesn't exist for course AND course run, so return a proxy record instead.
            return ProxyDataSharingConsent(**original_kwargs)


class DataSharingConsentManager(models.Manager.from_queryset(DataSharingConsentQuerySet)):  # pylint: disable=no-member
    """
    Model manager for :class:`.DataSharingConsent` model.

    Uses a QuerySet that returns a ``ProxyDataSharingConsent`` object when the searched-for
    ``DataSharingConsent`` object does not exist. Otherwise behaves the same as a normal manager.
    """


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
        for key, value in kwargs.items():
            if str(key).startswith('enterprise_customer__'):
                enterprise_customer_detail = key[len('enterprise_customer__'):]
                ec_keys[enterprise_customer_detail] = value

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
        usernames = set(child.username for child in children)
        enterprises = set(child.enterprise_customer for child in children)
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


class DataSharingConsent(ConsentModelMixin, Consent):  # pylint: disable=model-no-explicit-unicode
    """
    An abstract representation of Data Sharing Consent granted to an Enterprise for a course by a User.

    The model is used to store a persistent, historical consent state for users granting, not granting, or revoking
    data sharing consent to an Enterprise for a course.

    .. pii: The username field inherited from Consent contains PII.
    .. pii_types: username
    .. pii_retirement: consumer_api
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


@python_2_unicode_compatible
class DataSharingConsentTextOverrides(TimeStampedModel):
    """
    Stores texts overrides for data sharing consent page.

    .. no_pii:
    """

    class Meta:
        app_label = 'consent'
        verbose_name_plural = _('Data sharing consent text overrides')

    TOP_PARAGRAPH_HELP_TEXT = mark_safe_lazy(_(
        'Fill in a text for first paragraph of page. The following variables may be available:<br />'
        '<ul>'
        '<li>enterprise_customer_name: A name of enterprise customer.</li>'
        '<li>platform_name: Name of platform.</li>'
        '<li>item: A string which is "course" or "program" depending on the type of consent.</li>'
        '<li>course_title: Title of course. Available when type of consent is course.</li>'
        '<li>course_start_date: Course start date. Available when type of consent is course.</li>'
        '</ul>'
    ))
    POLICY_PARAGRAPH_HELP_TEXT = mark_safe_lazy(_(
        'Fill in a text for policy paragraph at the bottom of page. The following variables may be available:<br />'
        '<ul>'
        '<li>enterprise_customer_name: A name of enterprise customer.</li>'
        '<li>platform_name: Name of platform.</li>'
        '<li>item: A string which is "course" or "program" depending on the type of consent.</li>'
        '<li>course_title: Title of course. Available when type of consent is course.</li>'
        '<li>course_start_date: Course start date. Available when type of consent is course.</li>'
        '</ul>'
    ))
    SIDEBAR_PARAGRAPH_HELP_TEXT = mark_safe_lazy(_(
        'Fill in a text for left sidebar paragraph. The following variables may be available:<br />'
        '<ul>'
        '<li>enterprise_customer_name: A name of enterprise customer.</li>'
        '<li>platform_name: Name of platform.</li>'
        '<li>item: A string which is "course" or "program" depending on the type of consent.</li>'
        '<li>course_title: Title of course. Available when type of consent is course.</li>'
        '<li>course_start_date: Course start date. Available when type of consent is course.</li>'
        '</ul>'
    ))
    CONFIRMATION_MODAL_HELP_TEXT = mark_safe_lazy(_(
        'Fill in a text for dialog which appears when user decline to provide consent. '
        'The following variables may be available:<br />'
        '<ul>'
        '<li>enterprise_customer_name: A name of enterprise customer.</li>'
        '<li>item: A string which is "course" or "program" depending on the type of consent.</li>'
        '<li>course_title: Title of course. Available when type of consent is course.</li>'
        '<li>course_start_date: Course start date. Available when type of consent is course.</li>'
        '</ul>'
    ))
    NOTIFICATION_TITLE_HELP_TEXT = mark_safe_lazy(_(
        'Fill in a text for title of the notification which appears on dashboard '
        'when user decline to provide consent. '
        'The following variables may be available:<br />'
        '<ul>'
        '<li>enterprise_customer_name: A name of enterprise customer.</li>'
        '<li>course_title: Title of course. Available when type of consent is course.</li>'
        '</ul>'
    ))
    NOTIFICATION_MESSAGE_HELP_TEXT = mark_safe_lazy(_(
        'Fill in a text for message of the notification which appears on dashboard '
        'when user decline to provide consent. '
        'The following variables may be available:<br />'
        '<ul>'
        '<li>enterprise_customer_name: A name of enterprise customer.</li>'
        '<li>course_title: Title of course. Available when type of consent is course.</li>'
        '</ul>'
    ))

    page_title = models.CharField(
        max_length=255,
        help_text=_('Title of page')
    )
    left_sidebar_text = models.TextField(
        null=True,
        blank=True,
        help_text=SIDEBAR_PARAGRAPH_HELP_TEXT
    )
    top_paragraph = models.TextField(
        null=True,
        blank=True,
        help_text=TOP_PARAGRAPH_HELP_TEXT
    )
    agreement_text = models.TextField(
        null=True,
        blank=True,
        help_text=_('Text next to agreement check mark')
    )
    continue_text = models.CharField(
        max_length=255,
        help_text=_('Text of agree button')
    )
    abort_text = models.CharField(
        max_length=255,
        help_text=_('Text of decline link')
    )
    policy_dropdown_header = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text=_('Text of policy drop down')
    )
    policy_paragraph = models.TextField(
        null=True,
        blank=True,
        help_text=POLICY_PARAGRAPH_HELP_TEXT
    )
    confirmation_modal_header = models.CharField(
        max_length=255,
        help_text=_('Heading text of dialog box which appears when user decline to provide consent')
    )
    confirmation_modal_text = models.TextField(
        help_text=CONFIRMATION_MODAL_HELP_TEXT
    )
    modal_affirm_decline_text = models.CharField(
        max_length=255,
        help_text=_('Text of decline button on confirmation dialog box')
    )
    modal_abort_decline_text = models.CharField(
        max_length=255,
        help_text=_('Text of abort decline link on confirmation dialog box')
    )
    declined_notification_title = models.TextField(
        help_text=NOTIFICATION_TITLE_HELP_TEXT
    )
    declined_notification_message = models.TextField(
        help_text=NOTIFICATION_MESSAGE_HELP_TEXT
    )
    enterprise_customer = models.OneToOneField(
        EnterpriseCustomer,
        related_name="data_sharing_consent_page",
        on_delete=models.deletion.CASCADE
    )
    published = models.BooleanField(
        default=False,
        help_text=_("Specifies whether data sharing consent page is published.")
    )

    def __str__(self):
        """
        Return human-readable string representation.
        """
        return 'DataSharingConsentTextOverrides for EnterpriseCustomer with UUID {}>'.format(
            self.enterprise_customer.uuid
        )

    def __repr__(self):
        """
        Return uniquely identifying string representation.
        """
        return self.__str__()
