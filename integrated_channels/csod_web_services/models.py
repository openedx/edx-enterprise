# -*- coding: utf-8 -*-
"""
Database models for Enterprise Integrated Channel CSOD Web Services.
"""

from __future__ import absolute_import, unicode_literals

import json
from logging import getLogger

from config_models.models import ConfigurationModel
from integrated_channels.integrated_channel.models import EnterpriseCustomerPluginConfiguration
from integrated_channels.csod_web_services.exporters.content_metadata import CSODWebServicesContentMetadataExporter
from integrated_channels.csod_web_services.exporters.learner_data import CSODWebServicesLearnerExporter
from integrated_channels.csod_web_services.transmitters.content_metadata import CSODWebServicesContentMetadataTransmitter
from integrated_channels.csod_web_services.transmitters.learner_data import CSODWebServicesLearnerTransmitter
from simple_history.models import HistoricalRecords

from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _

LOGGER = getLogger(__name__)


@python_2_unicode_compatible
class CSODWebServicesGlobalConfiguration(ConfigurationModel):
    """
    The global configuration for integrating with Cornerstone.
    """

    complete_learning_object_api_path = models.CharField(
        max_length=255,
        verbose_name="Complete Learning Object (LO) API Path",
        help_text="The API path for making POST/DELETE requests to mark a user as having completed a LO on CSOD."
    )

    create_learning_object_path = models.CharField(
        max_length=255,
        verbose_name="Create Learning Object (LO) API Path",
        help_text="The API path for making course metadata POST requests to create LOs on CSOD."
    )

    update_learning_object_path = models.CharField(
        max_length=255,
        verbose_name="Update Learning Object (LO) API Path",
        help_text="The API path for making course metadata POST requests to update LOs on CSOD."
    )

    session_token_api_path = models.CharField(
        max_length=255,
        verbose_name="Session Token API Path",
        help_text=(
            "The API path for making OAuth-related POST requests to Cornerstone. "
            "This will be used to gain the OAuth access token and secret which is required for other API calls."
        )
    )

    class Meta:
        app_label = 'csod_web_services'

    def __str__(self):
        """
        Return a human-readable string representation of the object.
        """
        return "<CSODWebServicesGlobalConfiguration with id {id}>".format(id=self.id)

    def __repr__(self):
        """
        Return uniquely identifying string representation.
        """
        return self.__str__()


@python_2_unicode_compatible
class CSODWebServicesEnterpriseCustomerConfiguration(EnterpriseCustomerPluginConfiguration):
    """
    The Enterprise-specific configuration we need for integrating with Cornerstone.
    """

    csod_lo_ws_base_url = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="CSOD Learning Object Web Services base URL",
        help_text="The LO Web Services domain of the customer's CSOD Instance."
    )

    csod_lms_ws_base_url = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="CSOD LMS Web Services base URL",
        help_text="The LMS Web Services domain of the customer's CSOD Instance."
    )

    csod_username = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="CSOD Username",
        help_text=(
            "The CSOD Username provided to the customer's Cornerstone instance. "
            "It is required for authenticating with their SOAP API."
        )
    )

    csod_user_password = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Degreed User Password",
        help_text=(
            "The Degreed User Password provided to the content provider by Degreed. "
            "It is required for authenticating with their SOAP API."
        )
    )

    provider = models.CharField(
        max_length=100,
        default='EDX',
        verbose_name="Provider Name",
        help_text="The provider name that is configured for this content provider in the customer's system."
    )

    key = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="API Client ID",
        help_text=(
            "The API Client ID provided to edX by the enterprise customer to be used to make API "
            "calls to Cornerstone on behalf of the customer."
        )
    )

    secret = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="API Client Secret",
        help_text=(
            "The API Client Secret provided to edX by the enterprise customer to be used to make API "
            "calls to Cornerstone on behalf of the customer."
        )
    )

    history = HistoricalRecords()

    class Meta:
        app_label = 'csod_web_services'

    def __str__(self):
        """
        Return human-readable string representation.
        """
        return "<CSODWebServicesEnterpriseCustomerConfiguration for Enterprise {enterprise_name}>".format(
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
        return 'CSODWS'


    def get_learner_data_transmitter(self):
        """
        Return a ``CSODWebServicesLearnerTransmitter`` instance.
        """
        return CSODWebServicesLearnerTransmitter(self)

    def get_learner_data_exporter(self, user):
        """
        Return a ``CSODWebServicesLearnerExporter`` instance.
        """
        return CSODWebServicesLearnerExporter(user, self)

    def get_content_metadata_transmitter(self):
        """
        Return a ``CSODWebServicesContentMetadataTransmitter`` instance.
        """
        return CSODWebServicesContentMetadataTransmitter(self)

    def get_content_metadata_exporter(self, user):
        """
        Return a ``CSODWebServicesContentMetadataExporter`` instance.
        """
        return CSODWebServicesContentMetadataExporter(user, self)


@python_2_unicode_compatible
class CSODWebServicesLearnerDataTransmissionAudit(models.Model):
    """
    The payload we sent to Cornerstone at a given point in time for an enterprise course enrollment.
    """

    csod_username = models.CharField(
        max_length=255,
        blank=False,
        null=False
    )

    enterprise_course_enrollment_id = models.PositiveIntegerField(
        blank=False,
        null=False
    )

    learning_object_id = models.CharField(
        max_length=255,
        blank=False,
        null=False,
        help_text="The LO ID which is used to uniquely identify the course for Cornerstone."
    )

    comment_string = models.CharField(
        max_length=255,
        blank=False,
        null=False,
        help_text="The comment containing details for a learner's course completion sent to Cornerstone."
    )

    # Request-related information.
    status = models.CharField(max_length=100, blank=False, null=False)
    error_message = models.TextField(blank=True)
    # The completion time is the time of the request to Cornerstone's system.
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'csod_web_services'

    def __str__(self):
        """
        Return a human-readable string representation of the object.
        """
        return (
            '<CSODWebServicesLearnerDataTransmissionAudit {transmission_id}'.format(
                transmission_id=self.id,
            )
        )

    def __repr__(self):
        """
        Return uniquely identifying string representation.
        """
        return self.__str__()

    def serialize(self, *args, **kwargs):  # pylint: disable=unused-argument
        """
        Return a XML-serialized representation.

        Sort the keys so the result is consistent and testable.
        """
        return json.dumps(self._payload_data(), sort_keys=True)

    def _payload_data(self):
        """
        Convert the audit record's fields into Cornerstone key/value pairs.
        """
        return dict()
