"""
Database models for Enterprise Integrated Channel Degreed.
"""

import json
from logging import getLogger

from config_models.models import ConfigurationModel

from django.db import models

from integrated_channels.degreed.exporters.content_metadata import DegreedContentMetadataExporter
from integrated_channels.degreed.exporters.learner_data import DegreedLearnerExporter
from integrated_channels.degreed.transmitters.content_metadata import DegreedContentMetadataTransmitter
from integrated_channels.degreed.transmitters.learner_data import DegreedLearnerTransmitter
from integrated_channels.integrated_channel.models import (
    EnterpriseCustomerPluginConfiguration,
    LearnerDataTransmissionAudit,
)
from integrated_channels.utils import is_valid_url

LOGGER = getLogger(__name__)


class DegreedGlobalConfiguration(ConfigurationModel):
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
        app_label = 'degreed'

    def __str__(self):
        """
        Return a human-readable string representation of the object.
        """
        return "<DegreedGlobalConfiguration with id {id}>".format(id=self.id)

    def __repr__(self):
        """
        Return uniquely identifying string representation.
        """
        return self.__str__()


class DegreedEnterpriseCustomerConfiguration(EnterpriseCustomerPluginConfiguration):
    """
    The Enterprise-specific configuration we need for integrating with Degreed.

    .. no_pii:
    """

    key = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name="API Client ID",
        help_text=(
            "The API Client ID provided to edX by the enterprise customer to be used to make API "
            "calls to Degreed on behalf of the customer."
        )
    )

    secret = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name="API Client Secret",
        help_text=(
            "The API Client Secret provided to edX by the enterprise customer to be used to make API "
            "calls to Degreed on behalf of the customer."
        )
    )

    degreed_company_id = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name="Degreed Organization Code",
        help_text="The organization code provided to the enterprise customer by Degreed."
    )

    degreed_base_url = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name="Degreed Base URL",
        help_text="The base URL used for API requests to Degreed, i.e. https://degreed.com."
    )

    degreed_user_id = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name="Degreed User ID",
        help_text=(
            "The Degreed User ID provided to the content provider by Degreed. "
            "It is required for getting the OAuth access token."
        )
    )

    degreed_user_password = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name="Degreed User Password",
        help_text=(
            "The Degreed User Password provided to the content provider by Degreed. "
            "It is required for getting the OAuth access token."
        )
    )

    provider_id = models.CharField(
        max_length=100,
        default='EDX',
        verbose_name="Provider Code",
        help_text="The provider code that Degreed gives to the content provider."
    )

    class Meta:
        app_label = 'degreed'

    @property
    def is_valid(self):
        """
        Returns whether or not the configuration is valid and ready to be activated

        Args:
            obj: The instance of DegreedEnterpriseCustomerConfiguration
                being rendered with this admin form.
        """
        missing_items = {'missing': []}
        incorrect_items = {'incorrect': []}
        if not self.key:
            missing_items.get('missing').append('key')
        if not self.secret:
            missing_items.get('missing').append('secret')
        if not self.degreed_company_id:
            missing_items.get('missing').append('degreed_company_id')
        if not self.degreed_base_url:
            missing_items.get('missing').append('degreed_base_url')
        if not self.degreed_user_id:
            missing_items.get('missing').append('degreed_user_id')
        if not self.degreed_user_password:
            missing_items.get('missing').append('degreed_user_password')
        if not self.provider_id:
            missing_items.get('missing').append('provider_id')
        if not is_valid_url(self.degreed_base_url):
            incorrect_items.get('incorrect').append('degreed_base_url')
        if len(self.display_name) > 20:
            incorrect_items.get('incorrect').append('display_name')
        return missing_items, incorrect_items

    def __str__(self):
        """
        Return human-readable string representation.
        """
        return "<DegreedEnterpriseCustomerConfiguration for Enterprise {enterprise_name}>".format(
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
        return 'DEGREED'

    def get_learner_data_transmitter(self):
        """
        Return a ``DegreedLearnerTransmitter`` instance.
        """
        return DegreedLearnerTransmitter(self)

    def get_learner_data_exporter(self, user):
        """
        Return a ``DegreedLearnerDataExporter`` instance.
        """
        return DegreedLearnerExporter(user, self)

    def get_content_metadata_transmitter(self):
        """
        Return a ``DegreedContentMetadataTransmitter`` instance.
        """
        return DegreedContentMetadataTransmitter(self)

    def get_content_metadata_exporter(self, user):
        """
        Return a ``DegreedContentMetadataExporter`` instance.
        """
        return DegreedContentMetadataExporter(user, self)


class DegreedLearnerDataTransmissionAudit(LearnerDataTransmissionAudit):
    """
    The payload we sent to Degreed at a given point in time for an enterprise course enrollment.

    .. pii: The user_email AND degreed_user_email model fields contain PII.
    .. pii_types: email_address
    .. pii_retirement: consumer_api
    """

    degreed_user_email = models.CharField(
        max_length=255,
        blank=False,
        null=False
    )

    degreed_completed_timestamp = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        help_text=(
            'Represents the Degreed representation of a timestamp: yyyy-mm-dd, '
            'which is always 10 characters.'
        )
    )

    class Meta:
        app_label = 'degreed'
        index_together = ['enterprise_customer_uuid', 'plugin_configuration_id']

    def __str__(self):
        """
        Return a human-readable string representation of the object.
        """
        return (
            '<DegreedLearnerDataTransmissionAudit {transmission_id} for enterprise enrollment {enrollment}, '
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
            - `enterprise_configuration`: used to get the `degreed_company_id` to be sent in the payload.

        # TODO: When we refactor to use a serialization flow consistent with how course metadata
        # is serialized, remove the serialization here and make the learner data exporter handle the work.
        """
        enterprise_configuration = kwargs.get('enterprise_configuration')
        degreed_company_id = enterprise_configuration.degreed_company_id \
            if hasattr(enterprise_configuration, 'degreed_company_id') else ''
        json_payload = {
            'orgCode': degreed_company_id,
            'completions': [{
                'email': self.degreed_user_email,
                'id': self.course_id,
                'completionDate': self.degreed_completed_timestamp,
            }]
        }
        return json.dumps(json_payload, sort_keys=True)
