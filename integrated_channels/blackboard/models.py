# -*- coding: utf-8 -*-
"""
Database models for Enterprise Integrated Channel Blackboard.
"""

import json
from logging import getLogger

from simple_history.models import HistoricalRecords

from django.db import models
from django.utils.encoding import python_2_unicode_compatible

from integrated_channels.blackboard.exporters.content_metadata import BlackboardContentMetadataExporter
from integrated_channels.blackboard.exporters.learner_data import BlackboardLearnerExporter
from integrated_channels.blackboard.transmitters.content_metadata import BlackboardContentMetadataTransmitter
from integrated_channels.blackboard.transmitters.learner_data import BlackboardLearnerTransmitter
from integrated_channels.integrated_channel.models import EnterpriseCustomerPluginConfiguration

LOGGER = getLogger(__name__)


@python_2_unicode_compatible
class BlackboardEnterpriseCustomerConfiguration(EnterpriseCustomerPluginConfiguration):
    """
    The Enterprise-specific configuration we need for integrating with Blackboard.

    .. no_pii:
    """

    client_id = models.CharField(
        max_length=255,
        null=True,
        verbose_name="API Client ID or Blackboard Application Key",
        help_text=(
            "The API Client ID provided to edX by the enterprise customer to be used to make API "
            "calls on behalf of the customer. Called Application Key in Blackboard"
        )
    )

    client_secret = models.CharField(
        max_length=255,
        null=True,
        verbose_name="API Client Secret or Application Secret",
        help_text=(
            "The API Client Secret provided to edX by the enterprise customer to be used to make "
            " API calls on behalf of the customer. Called Application Secret in Blackboard"
        )
    )

    blackboard_base_url = models.CharField(
        max_length=255,
        null=True,
        verbose_name="Base URL",
        help_text="The base URL used for API requests to Blackboard, i.e. https://blackboard.com."
    )

    refresh_token = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Oauth2 Refresh Token",
        help_text="The refresh token provided by Blackboard along with the access token request,"
                  "used to re-request the access tokens over multiple client sessions."
    )

    # overriding base model field, to use chunk size 1 default
    transmission_chunk_size = models.IntegerField(
        default=1,
        help_text=(
            "The maximum number of data items to transmit to the integrated channel "
            "with each request."
        )
    )

    history = HistoricalRecords()

    class Meta:
        app_label = 'blackboard'

    def __str__(self):
        """
        Return human-readable string representation.
        """
        return "<BlackboardEnterpriseCustomerConfiguration for Enterprise {enterprise_name}>".format(
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
        return 'BLACKBOARD'

    def get_content_metadata_exporter(self, user):
        return BlackboardContentMetadataExporter(user, self)

    def get_content_metadata_transmitter(self):
        return BlackboardContentMetadataTransmitter(self)

    def get_learner_data_exporter(self, user):
        return BlackboardLearnerExporter(user, self)

    def get_learner_data_transmitter(self):
        return BlackboardLearnerTransmitter(self)


@python_2_unicode_compatible
class BlackboardLearnerDataTransmissionAudit(models.Model):
    """
    The payload we send to Blackboard at a given point in time for an enterprise course enrollment.

    """
    blackboard_user_email = models.EmailField(
        max_length=255,
        blank=False,
        null=False,
        help_text='The learner`s Blackboard email. This must match the email on edX in'
                  ' order for both learner and content metadata integrations.'
    )
    completed_timestamp = models.CharField(
        max_length=10,
        help_text=(
            'Represents the Blackboard representation of a timestamp: yyyy-mm-dd, '
            'which is always 10 characters.'
        )
    )
    course_id = models.CharField(max_length=255, blank=False, null=False)
    course_completed = models.BooleanField(
        default=True,
        help_text="The learner's course completion status transmitted to Blackboard."
    )
    enterprise_course_enrollment_id = models.PositiveIntegerField(blank=False, null=False, db_index=True)
    grade = models.DecimalField(blank=True, null=True, max_digits=3, decimal_places=2)
    total_hours = models.FloatField(null=True, blank=True)

    # Request-related information.
    created = models.DateTimeField(auto_now_add=True)
    error_message = models.TextField(blank=True)
    status = models.CharField(max_length=100, blank=False, null=False)

    class Meta:
        app_label = 'blackboard'

    def __str__(self):
        """
        Return a human-readable string representation of the object.
        """
        return (
            '<BlackboardLearnerDataTransmissionAudit {transmission_id} for enterprise enrollment '
            '{enterprise_course_enrollment_id}, Blackboard user {blackboard_user_email}, '
            'and course {course_id}>'.format(
                transmission_id=self.id,
                enterprise_course_enrollment_id=self.enterprise_course_enrollment_id,
                blackboard_user_email=self.blackboard_user_email,
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

        # TODO: When we refactor to use a serialization flow consistent with how course metadata
        # is serialized, remove the serialization here and make the learner data exporter handle the work.
        """
        return json.dumps(self._payload_data(), sort_keys=True)

    def _payload_data(self):
        """
        Convert the audit record's fields into Blackboard key/value pairs.
        """
        return dict(
            userID=self.blackboard_user_email,
            courseID=self.course_id,
            courseCompleted="true" if self.course_completed else "false",
            completedTimestamp=self.completed_timestamp,
            grade=self.grade,
            totalHours=self.total_hours,
        )
