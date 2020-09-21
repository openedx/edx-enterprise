# -*- coding: utf-8 -*-
"""
Database models for Enterprise Integrated Channel Moodle.
"""

from logging import getLogger

from simple_history.models import HistoricalRecords

from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _

from integrated_channels.integrated_channel.models import EnterpriseCustomerPluginConfiguration
from integrated_channels.moodle.exporters.content_metadata import MoodleContentMetadataExporter
from integrated_channels.moodle.transmitters.content_metadata import MoodleContentMetadataTransmitter

LOGGER = getLogger(__name__)


# pylint: disable=feature-toggle-needs-doc
@python_2_unicode_compatible
class MoodleEnterpriseCustomerConfiguration(EnterpriseCustomerPluginConfiguration):
    """
    The Enterprise-specific configuration we need for integrating with Moodle.

    .. no_pii:
    """

    moodle_base_url = models.CharField(
        max_length=255,
        verbose_name="Moodle Base URL",
        help_text=_("The base URL used for API requests to Moodle")
    )

    service_short_name = models.CharField(
        max_length=255,
        verbose_name="Webservice Short Name",
        help_text=_(
            "The short name for the Moodle webservice."
        )
    )

    category_id = models.IntegerField(
        blank=True,
        null=True,
        verbose_name="Category ID",
        help_text=_(
            "The category ID for what edX courses should be associated with."
        )
    )

    username = models.CharField(
        max_length=255,
        verbose_name="Webservice Username",
        blank=True,
        null=True,
        help_text=_(
            "The API user's username used to obtain new tokens."
        )
    )

    password = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Webservice Password",
        help_text=_(
            "The API user's password used to obtain new tokens."
        )
    )

    token = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Webservice User Token",
        help_text=_(
            "The user's token for the Moodle webservice."
        )
    )

    history = HistoricalRecords()

    class Meta:
        app_label = 'moodle'

    def __str__(self):
        """
        Return human-readable string representation.
        """
        return "<MoodleEnterpriseCustomerConfiguration for Enterprise {enterprise_name}>".format(
            enterprise_name=self.enterprise_customer.name
        )

    def __repr__(self):
        """
        Return uniquely identifying string representation.
        """
        return self.__str__()

    @staticmethod
    def channel_code():
        """
        Returns an capitalized identifier for this channel class, unique among subclasses.
        """
        return 'MOODLE'

    def get_content_metadata_exporter(self, user):
        return MoodleContentMetadataExporter(user, self)

    def get_content_metadata_transmitter(self):
        return MoodleContentMetadataTransmitter(self)
