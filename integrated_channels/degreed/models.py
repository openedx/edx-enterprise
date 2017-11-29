# -*- coding: utf-8 -*-
"""
Database models for Enterprise Integrated Channel Degreed.
"""

from __future__ import absolute_import, unicode_literals

import json
from logging import getLogger

from config_models.models import ConfigurationModel
from integrated_channels.degreed.exporters.course_metadata import DegreedCourseExporter
from integrated_channels.degreed.exporters.learner_data import DegreedLearnerExporter
from integrated_channels.degreed.transmitters.course_metadata import DegreedCourseTransmitter
from integrated_channels.degreed.transmitters.learner_data import DegreedLearnerTransmitter
from integrated_channels.integrated_channel.models import EnterpriseCustomerPluginConfiguration
from simple_history.models import HistoricalRecords

from django.db import models
from django.utils.encoding import python_2_unicode_compatible

LOGGER = getLogger(__name__)


@python_2_unicode_compatible
class DegreedGlobalConfiguration(ConfigurationModel):
    """
    The global configuration for integrating with Degreed.
    """

    degreed_base_url = models.CharField(
        max_length=255,
        verbose_name="Degreed Base URL",
        help_text="The base URL used for API requests to Degreed, i.e. https://degreed.com."
    )

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

    degreed_user_id = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Degreed User ID",
        help_text=(
            "The Degreed User ID provided to the content provider by Degreed. "
            "It is required for getting the OAuth access token."
        )
    )

    degreed_user_password = models.CharField(
        max_length=255,
        blank=True,
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


@python_2_unicode_compatible
class DegreedEnterpriseCustomerConfiguration(EnterpriseCustomerPluginConfiguration):
    """
    The Enterprise-specific configuration we need for integrating with Degreed.
    """

    key = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="API Client ID",
        help_text=(
            "The API Client ID provided to edX by the enterprise customer to be used to make API "
            "calls to Degreed on behalf of the customer."
        )
    )

    secret = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="API Client Secret",
        help_text=(
            "The API Client Secret provided to edX by the enterprise customer to be used to make API "
            "calls to Degreed on behalf of the customer."
        )
    )

    degreed_company_id = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Degreed Organization Code",
        help_text="The organization code provided to the enterprise customer by Degreed."
    )

    history = HistoricalRecords()

    class Meta:
        app_label = 'degreed'

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

    @property
    def provider_id(self):
        '''
        Fetch ``provider_id`` from global configuration settings
        '''
        return DegreedGlobalConfiguration.current().provider_id

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

    def get_course_data_transmitter(self):
        """
        Return a ``DegreedCourseTransmitter`` instance.
        """
        return DegreedCourseTransmitter(self)

    def get_course_data_exporter(self, user):
        """
        Return a ``DegreedCourseExporter`` instance.
        """
        return DegreedCourseExporter(user, self)


@python_2_unicode_compatible
class DegreedLearnerDataTransmissionAudit(models.Model):
    """
    The payload we sent to Degreed at a given point in time for an enterprise course enrollment.
    """

    degreed_user_email = models.CharField(
        max_length=255,
        blank=False,
        null=False
    )

    enterprise_course_enrollment_id = models.PositiveIntegerField(
        blank=False,
        null=False
    )

    course_id = models.CharField(
        max_length=255,
        blank=False,
        null=False,
        help_text="The course run's key which is used to uniquely identify the course for Degreed."
    )

    course_completed = models.BooleanField(
        default=True,
        help_text="The learner's course completion status transmitted to Degreed."
    )

    completed_timestamp = models.CharField(
        max_length=10,
        help_text=(
            'Represents the Degreed representation of a timestamp: yyyy-mm-dd, '
            'which is always 10 characters.'
        )
    )

    # Request-related information.
    status = models.CharField(max_length=100, blank=False, null=False)
    error_message = models.TextField(blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'degreed'

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
