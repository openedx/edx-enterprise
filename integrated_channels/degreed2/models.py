# -*- coding: utf-8 -*-
"""
Database models for Enterprise Integrated Channel Degreed.
"""

from logging import getLogger

from simple_history.models import HistoricalRecords

from django.db import models

from integrated_channels.degreed2.exporters.content_metadata import Degreed2ContentMetadataExporter
from integrated_channels.degreed2.exporters.learner_data import Degreed2LearnerExporter
from integrated_channels.degreed2.transmitters.content_metadata import Degreed2ContentMetadataTransmitter
from integrated_channels.degreed2.transmitters.learner_data import Degreed2LearnerTransmitter
from integrated_channels.integrated_channel.models import EnterpriseCustomerPluginConfiguration

LOGGER = getLogger(__name__)


class Degreed2EnterpriseCustomerConfiguration(EnterpriseCustomerPluginConfiguration):
    """
    The Enterprise-specific configuration we need for integrating with Degreed2.

    .. no_pii:
    """

    client_id = models.CharField(
        max_length=255,
        verbose_name="API Client ID",
        help_text=(
            "The API Client ID provided to edX by the enterprise customer to be used to make API "
            "calls to Degreed on behalf of the customer."
        )
    )

    client_secret = models.CharField(
        max_length=255,
        verbose_name="API Client Secret",
        help_text=(
            "The API Client Secret provided to edX by the enterprise customer to be used to make API "
            "calls to Degreed on behalf of the customer."
        )
    )

    degreed_base_url = models.CharField(
        max_length=255,
        verbose_name="Degreed Base URL",
        help_text="The base URL used for API requests to Degreed, i.e. https://degreed.com."
    )

    degreed_token_fetch_base_url = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="Degreed token fetch base url",
        help_text="If provided, will be used as base url instead of degreed_base_url to fetch tokens"
    )

    history = HistoricalRecords()

    class Meta:
        app_label = 'degreed2'

    def __str__(self):
        """
        Return human-readable string representation.
        """
        return "<Degreed2EnterpriseCustomerConfiguration for Enterprise {enterprise_name}>".format(
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
        return 'DEGREED2'

    def get_learner_data_transmitter(self):
        """
        Return a ``DegreedLearnerTransmitter`` instance.
        """
        return Degreed2LearnerTransmitter(self)

    def get_learner_data_exporter(self, user):
        """
        Return a ``DegreedLearnerDataExporter`` instance.
        """
        return Degreed2LearnerExporter(user, self)

    def get_content_metadata_transmitter(self):
        """
        Return a ``DegreedContentMetadataTransmitter`` instance.
        """
        return Degreed2ContentMetadataTransmitter(self)

    def get_content_metadata_exporter(self, user):
        """
        Return a ``DegreedContentMetadataExporter`` instance.
        """
        return Degreed2ContentMetadataExporter(user, self)


class Degreed2LearnerDataTransmissionAudit(models.Model):
    """
    The payload we sent to Degreed2 at a given point in time for an enterprise course enrollment.
    Ref: https://api.degreed.com/docs/#create-a-new-completion

    .. pii: The degreed_user_email model field contains PII.
    .. pii_types: email_address
    .. pii_retirement: consumer_api
    """

    degreed_user_email = models.CharField(
        max_length=255,
        blank=False,
        null=False,
        help_text='Used as the user-id field when creating a completion',
    )

    enterprise_course_enrollment_id = models.PositiveIntegerField(
        blank=False,
        null=False,
        db_index=True
    )

    course_id = models.CharField(
        max_length=255,
        blank=False,
        null=False,
        help_text="Used as content-id field when creating a completion"
    )

    completed_timestamp = models.CharField(
        max_length=19,
        help_text='yyyy-mm-ddTHH:MM:SS format',
    )

    # Request-related information.
    status = models.CharField(max_length=100, blank=False, null=False)
    error_message = models.TextField(blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'degreed2'

    def __str__(self):
        """
        Return a human-readable string representation of the object.
        """
        return (
            '<Degreed2LearnerDataTransmissionAudit {transmission_id} for enterprise enrollment {enrollment}, '
            'email {degreed_user_email}, and course {course_id}>'.format(
                transmission_id=self.id,
                enrollment=self.enterprise_course_enrollment_id,
                degreed_user_email=self.degreed_user_email,
                course_id=self.course_id
            )
        )

    def __repr__(self):
        """
        Return uniquely identifying string representation.
        """
        return self.__str__()
