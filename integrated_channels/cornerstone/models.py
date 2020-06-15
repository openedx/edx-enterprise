# -*- coding: utf-8 -*-
"""
Database models for Enterprise Integrated Channel Cornerstone.
"""

import json
from logging import getLogger

from config_models.models import ConfigurationModel
from jsonfield import JSONField
from simple_history.models import HistoricalRecords

from django.contrib.auth.models import User
from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _

from model_utils.models import TimeStampedModel

from integrated_channels.cornerstone.exporters.content_metadata import CornerstoneContentMetadataExporter
from integrated_channels.cornerstone.exporters.learner_data import CornerstoneLearnerExporter
from integrated_channels.cornerstone.transmitters.content_metadata import CornerstoneContentMetadataTransmitter
from integrated_channels.cornerstone.transmitters.learner_data import CornerstoneLearnerTransmitter
from integrated_channels.integrated_channel.models import EnterpriseCustomerPluginConfiguration

LOGGER = getLogger(__name__)


# pylint: disable=feature-toggle-needs-doc
@python_2_unicode_compatible
class CornerstoneGlobalConfiguration(ConfigurationModel):
    """
    The global configuration for integrating with Cornerstone.

    .. no_pii:
    """

    completion_status_api_path = models.CharField(
        max_length=255,
        verbose_name="Completion Status API Path",
        help_text=_("The API path for making completion POST requests to Cornerstone.")
    )

    oauth_api_path = models.CharField(
        max_length=255,
        verbose_name="OAuth API Path",
        help_text=_(
            "The API path for making OAuth-related POST requests to Cornerstone. "
            "This will be used to gain the OAuth access token which is required for other API calls."
        )
    )

    key = models.CharField(
        max_length=255,
        default='key',
        verbose_name="Basic Auth username",
        help_text=_('Basic auth username for sending user completion status to cornerstone.')
    )
    secret = models.CharField(
        max_length=255,
        default='secret',
        verbose_name="Basic Auth password",
        help_text=_('Basic auth password for sending user completion status to cornerstone.')
    )

    subject_mapping = JSONField(
        default={},
        help_text=_("Key/value mapping cornerstone subjects to edX subjects list"),
    )

    languages = JSONField(
        default={},
        help_text=_("List of IETF language tags supported by cornerstone"),
    )

    class Meta:
        app_label = 'cornerstone'

    def __str__(self):
        """
        Return a human-readable string representation of the object.
        """
        return "<CornerstoneGlobalConfiguration with id {id}>".format(id=self.id)

    def __repr__(self):
        """
        Return uniquely identifying string representation.
        """
        return self.__str__()


@python_2_unicode_compatible
class CornerstoneEnterpriseCustomerConfiguration(EnterpriseCustomerPluginConfiguration):
    """
    The Enterprise-specific configuration we need for integrating with Cornerstone.

    .. no_pii:
    """
    cornerstone_base_url = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Cornerstone Base URL",
        help_text=_("The base URL used for API requests to Cornerstone, i.e. https://portalName.csod.com")
    )

    history = HistoricalRecords()

    class Meta:
        app_label = 'cornerstone'

    def __str__(self):
        """
        Return human-readable string representation.
        """
        return "<CornerstoneEnterpriseCustomerConfiguration for Enterprise {enterprise_name}>".format(
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
        return 'CSOD'

    def get_content_metadata_transmitter(self):
        """
        Return a ``CornerstoneContentMetadataTransmitter`` instance.
        """
        return CornerstoneContentMetadataTransmitter(self)

    def get_content_metadata_exporter(self, user):
        """
        Return a ``CornerstoneContentMetadataExporter`` instance.
        """
        return CornerstoneContentMetadataExporter(user, self)

    def get_learner_data_transmitter(self):
        """
        Return a ``CornerstoneLearnerTransmitter`` instance.
        """
        return CornerstoneLearnerTransmitter(self)

    def get_learner_data_exporter(self, user):
        """
        Return a ``CornerstoneLearnerExporter`` instance.
        """
        return CornerstoneLearnerExporter(user, self)


@python_2_unicode_compatible
class CornerstoneLearnerDataTransmissionAudit(TimeStampedModel):
    """
    The payload we sent to Cornerstone at a given point in time for an enterprise course enrollment.

    """
    user = models.ForeignKey(
        User,
        blank=False,
        null=False,
        related_name='cornerstone_transmission_audit',
        on_delete=models.CASCADE,
    )

    user_guid = models.CharField(
        max_length=255,
        blank=False,
        null=False
    )

    enterprise_course_enrollment_id = models.PositiveIntegerField(
        blank=True,
        null=True,
        db_index=True,
    )

    course_id = models.CharField(
        max_length=255,
        blank=False,
        null=False,
        help_text=_("The course run's key which is used to uniquely identify the course for Cornerstone.")
    )

    session_token = models.CharField(max_length=255, null=False, blank=False)
    callback_url = models.CharField(max_length=255, null=False, blank=False)
    subdomain = models.CharField(max_length=255, null=False, blank=False)

    course_completed = models.BooleanField(
        default=False,
        help_text=_("The learner's course completion status transmitted to Cornerstone.")
    )

    completed_timestamp = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_(
            'Date time when user completed course'
        )
    )
    grade = models.CharField(max_length=255, null=True, blank=True)
    # Request-related information.
    status = models.CharField(max_length=100, blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)

    class Meta:
        app_label = 'cornerstone'
        unique_together = ("user", "course_id")

    def __str__(self):
        """
        Return a human-readable string representation of the object.
        """
        return (
            '<CornerstoneLearnerDataTransmissionAudit {transmission_id} for enterprise enrollment {enrollment}, '
            'guid {user_guid}, and course {course_id}>'.format(
                transmission_id=self.id,
                enrollment=self.enterprise_course_enrollment_id,
                user_guid=self.user_guid,
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
        """
        data = {
            'courseId': self.course_id,
            'userGuid': self.user_guid,
            'callbackUrl': self.callback_url,
            'sessionToken': self.session_token,
            'status': 'Completed' if self.grade in ['Pass', 'Fail'] else 'In Progress',
            'completionDate':
                self.completed_timestamp.replace(microsecond=0).isoformat() if self.completed_timestamp else None,
        }
        if self.grade != 'In Progress':
            data['successStatus'] = self.grade
        return json.dumps(
            {
                "data": data
            },
            sort_keys=True
        )
