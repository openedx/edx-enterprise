# -*- coding: utf-8 -*-
"""
Database models for Enterprise Integrated Channel Degreed.
"""

import json
from logging import getLogger

from simple_history.models import HistoricalRecords

from django.db import models

from integrated_channels.degreed2.exporters.content_metadata import Degreed2ContentMetadataExporter
from integrated_channels.degreed2.exporters.learner_data import Degreed2LearnerExporter
from integrated_channels.degreed2.transmitters.content_metadata import Degreed2ContentMetadataTransmitter
from integrated_channels.degreed2.transmitters.learner_data import Degreed2LearnerTransmitter
from integrated_channels.integrated_channel.models import (
    EnterpriseCustomerPluginConfiguration,
    LearnerDataTransmissionAudit,
)
from integrated_channels.utils import is_valid_url

LOGGER = getLogger(__name__)


class Degreed2EnterpriseCustomerConfiguration(EnterpriseCustomerPluginConfiguration):
    """
    The Enterprise-specific configuration we need for integrating with Degreed2.

    .. no_pii:
    """

    client_id = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name="API Client ID",
        help_text=(
            "The API Client ID provided to edX by the enterprise customer to be used to make API "
            "calls to Degreed on behalf of the customer."
        )
    )

    client_secret = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name="API Client Secret",
        help_text=(
            "The API Client Secret provided to edX by the enterprise customer to be used to make API "
            "calls to Degreed on behalf of the customer."
        )
    )

    degreed_base_url = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name="Degreed Base URL",
        help_text="The base URL used for API requests to Degreed, i.e. https://degreed.com."
    )

    degreed_token_fetch_base_url = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name="Degreed token fetch base url",
        help_text="If provided, will be used as base url instead of degreed_base_url to fetch tokens"
    )

    # overriding base model field, to use chunk size 1 default
    transmission_chunk_size = models.IntegerField(
        default=1,
        help_text="The maximum number of data items to transmit to the integrated channel with each request."
    )

    history = HistoricalRecords()

    class Meta:
        app_label = 'degreed2'

    @property
    def is_valid(self):
        """
        Returns whether or not the configuration is valid and ready to be activated

        Args:
            obj: The instance of Degreed2EnterpriseCustomerConfiguration
                being rendered with this admin form.
        """
        missing_items = {'missing': []}
        incorrect_items = {'incorrect': []}

        if not self.client_id:
            missing_items.get('missing').append('client_id')
        if not self.client_secret:
            missing_items.get('missing').append('client_secret')
        if not self.degreed_base_url:
            missing_items.get('missing').append('degreed_base_url')
        if not is_valid_url(self.degreed_token_fetch_base_url):
            incorrect_items.get('incorrect').append('degreed_token_fetch_base_url')
        if not is_valid_url(self.degreed_base_url):
            incorrect_items.get('incorrect').append('degreed_base_url')
        if len(self.display_name) > 20:
            incorrect_items.get('incorrect').append('display_name')
        return missing_items, incorrect_items

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


class Degreed2LearnerDataTransmissionAudit(LearnerDataTransmissionAudit):
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

    # XXX non-standard, should store datetime and export the format
    completed_timestamp = models.CharField(
        null=True,
        blank=True,
        max_length=19,
        help_text='yyyy-mm-ddTHH:MM:SS format. Can be left unset for audit records.',
    )

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

    def serialize(self, *args, **kwargs):
        """
        Return a JSON-serialized representation.

        Sort the keys so the result is consistent and testable.

        Can take the following keyword arguments:
            - `enterprise_configuration`
        """
        json_payload = {
            "data": {
                "attributes": {
                    "user-id": self.degreed_user_email,
                    "user-identifier-type": "Email",
                    "content-id": self.course_id,
                    "content-id-type": "externalId",
                    "content-type": "course",
                    "completed-at": self.completed_timestamp,
                }
            }
        }
        return json.dumps(json_payload, sort_keys=True)
