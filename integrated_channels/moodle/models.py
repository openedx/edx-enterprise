# -*- coding: utf-8 -*-
"""
Database models for Enterprise Integrated Channel Moodle.
"""

import json
from logging import getLogger

from simple_history.models import HistoricalRecords

from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _

from integrated_channels.integrated_channel.models import EnterpriseCustomerPluginConfiguration
from integrated_channels.moodle.exporters.content_metadata import MoodleContentMetadataExporter
from integrated_channels.moodle.exporters.learner_data import MoodleLearnerExporter
from integrated_channels.moodle.transmitters.content_metadata import MoodleContentMetadataTransmitter
from integrated_channels.moodle.transmitters.learner_data import MoodleLearnerTransmitter

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

    transmission_chunk_size = models.IntegerField(
        default=1,
        help_text=_("The maximum number of data items to transmit to the integrated channel with each request.")
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

    def get_learner_data_exporter(self, user):
        return MoodleLearnerExporter(user, self)

    def get_learner_data_transmitter(self):
        return MoodleLearnerTransmitter(self)

    def get_content_metadata_exporter(self, user):
        return MoodleContentMetadataExporter(user, self)

    def get_content_metadata_transmitter(self):
        return MoodleContentMetadataTransmitter(self)


@python_2_unicode_compatible
class MoodleLearnerDataTransmissionAudit(models.Model):
    """
    The payload we send to Moodle at a given point in time for an enterprise course enrollment.

    """
    moodle_user_email = models.EmailField(
        max_length=255,
        blank=False,
        null=False,
        help_text='The learner`s Moodle email. This must match the email on edX'
    )

    enterprise_course_enrollment_id = models.PositiveIntegerField(blank=False, null=False, db_index=True)
    course_id = models.CharField(max_length=255, blank=False, null=False)
    course_completed = models.BooleanField(default=False)
    grade = models.DecimalField(blank=True, null=True, max_digits=3, decimal_places=2)
    total_hours = models.FloatField(null=True, blank=True)
    course_completed = models.BooleanField(
        default=True,
        help_text="The learner's course completion status transmitted to Moodle."
    )
    completed_timestamp = models.CharField(
        max_length=10,
        help_text=(
            'Represents the Moodle representation of a timestamp: yyyy-mm-dd, '
            'which is always 10 characters.'
        )
    )

    # Request-related information.
    status = models.CharField(max_length=100, blank=False, null=False)
    error_message = models.TextField(blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'moodle'

    def __str__(self):
        """
        Return a human-readable string representation of the object.
        """
        return (
            '<MoodleLearnerDataTransmissionAudit {transmission_id} for enterprise enrollment '
            '{enterprise_course_enrollment_id}, Moodle user {moodle_user_email}, and course {course_id}>'.format(
                transmission_id=self.id,
                enterprise_course_enrollment_id=self.enterprise_course_enrollment_id,
                moodle_user_email=self.moodle_user_email,
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
        Convert the audit record's fields into Moodle key/value pairs.
        """
        return dict(
            userID=self.moodle_user_email,
            courseID=self.course_id,
            courseCompleted="true" if self.course_completed else "false",
            completedTimestamp=self.completed_timestamp,
            grade=self.grade,
            totalHours=self.total_hours,
        )
