# -*- coding: utf-8 -*-
"""
Database models for Enterprise Integrated Channel Degreed.
"""

import json
from logging import getLogger

from config_models.models import ConfigurationModel
from simple_history.models import HistoricalRecords

from django.db import models

from integrated_channels.degreed2.exporters.content_metadata import Degreed2ContentMetadataExporter
from integrated_channels.degreed2.exporters.learner_data import Degreed2LearnerExporter
from integrated_channels.degreed2.transmitters.content_metadata import Degreed2ContentMetadataTransmitter
from integrated_channels.degreed2.transmitters.learner_data import Degreed2LearnerTransmitter
from integrated_channels.integrated_channel.models import EnterpriseCustomerPluginConfiguration

LOGGER = getLogger(__name__)


class Degreed2GlobalConfiguration(ConfigurationModel):
    """
    The global configuration for integrating with Degreed.

    .. no_pii:
    """

    completion_status_api_path = models.CharField(
        max_length=255,
        verbose_name="Completion Status API Path",
        help_text="The API path for making completion POST/DELETE requests to Degreed."
    )

    course_api_path = models.CharField(
        max_length=255,
        verbose_name="Course Metadata API Path",
        help_text="The API path for making course metadata POST/DELETE requests to Degreed."
    )

    oauth_api_path = models.CharField(
        max_length=255,
        verbose_name="OAuth API Path",
        help_text=(
            "The API path for making OAuth-related POST requests to Degreed. "
            "This will be used to gain the OAuth access token which is required for other API calls."
        )
    )

    class Meta:
        app_label = 'degreed2'

    def __str__(self):
        """
        Return a human-readable string representation of the object.
        """
        return "<Degreed2GlobalConfiguration with id {id}>".format(id=self.id)

    def __repr__(self):
        """
        Return uniquely identifying string representation.
        """
        return self.__str__()


class Degreed2EnterpriseCustomerConfiguration(EnterpriseCustomerPluginConfiguration):
    """
    The Enterprise-specific configuration we need for integrating with Degreed2.

    .. no_pii:
    """

    key = models.CharField(
        max_length=255,
        verbose_name="API Client ID",
        help_text=(
            "The API Client ID provided to edX by the enterprise customer to be used to make API "
            "calls to Degreed on behalf of the customer."
        )
    )

    secret = models.CharField(
        max_length=255,
        verbose_name="API Client Secret",
        help_text=(
            "The API Client Secret provided to edX by the enterprise customer to be used to make API "
            "calls to Degreed on behalf of the customer."
        )
    )

    degreed_company_id = models.CharField(
        max_length=255,
        verbose_name="Degreed Organization Code",
        help_text="The organization code provided to the enterprise customer by Degreed."
    )

    degreed_base_url = models.CharField(
        max_length=255,
        verbose_name="Degreed Base URL",
        help_text="The base URL used for API requests to Degreed, i.e. https://degreed.com."
    )

    degreed_token_fetch_base_url = models.CharField(
        max_length=255,
        verbose_name="Degreed2 URL base to fetch tokens, separate from degreed_base_url",
        help_text="If provided, will be used as base url instead of degreed_base_url to fetch tokens"
    )

    provider_id = models.CharField(
        max_length=100,
        default='EDX',
        verbose_name="Provider Code",
        help_text="The provider code that Degreed gives to the content provider."
    )

    history = HistoricalRecords()

    class Meta:
        app_label = 'degreed'

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

    def serialize(self, *args, **kwargs):  # pylint: disable=unused-argument
        """
        Return a JSON-serialized representation.

        Sort the keys so the result is consistent and testable.

        Can take the following keyword arguments:
            - `enterprise_configuration`: used to get the `degreed_company_id` to be sent in the payload.

        # TODO: When we refactor to use a serialization flow consistent with how course metadata
        # is serialized, remove the serialization here and make the learner data exporter handle the work.
        """
        enterprise_configuration = kwargs.get('enterprise_configuration')
        degreed_company_id = enterprise_configuration.degreed_company_id \
            if hasattr(enterprise_configuration, 'degreed_company_id') else ''
        return json.dumps(self._payload_data(degreed_company_id), sort_keys=True)

    def _payload_data(self, degreed_company_id):
        """
        Convert the audit record's fields into Degreed key/value pairs.
        """
        return {
            'orgCode': degreed_company_id,
            'completions': [{
                'email': self.degreed_user_email,
                'id': self.course_id,
                'completionDate': self.completed_timestamp,
            }]
        }
