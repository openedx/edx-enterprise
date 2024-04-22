"""
Database models for Enterprise Integrated Channel Moodle.
"""

import json
from logging import getLogger

from fernet_fields import EncryptedCharField

from django.db import models
from django.utils.encoding import force_bytes, force_str
from django.utils.translation import gettext_lazy as _

from integrated_channels.integrated_channel.models import (
    EnterpriseCustomerPluginConfiguration,
    LearnerDataTransmissionAudit,
)
from integrated_channels.moodle.exporters.content_metadata import MoodleContentMetadataExporter
from integrated_channels.moodle.exporters.learner_data import MoodleLearnerExporter
from integrated_channels.moodle.transmitters.content_metadata import MoodleContentMetadataTransmitter
from integrated_channels.moodle.transmitters.learner_data import MoodleLearnerTransmitter
from integrated_channels.utils import is_valid_url

LOGGER = getLogger(__name__)


class MoodleEnterpriseCustomerConfiguration(EnterpriseCustomerPluginConfiguration):
    """
    The Enterprise-specific configuration we need for integrating with Moodle.

    .. no_pii:
    """

    moodle_base_url = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Moodle Base URL",
        help_text=_("The base URL used for API requests to Moodle")
    )

    service_short_name = models.CharField(
        max_length=255,
        blank=True,
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

    decrypted_username = EncryptedCharField(
        max_length=255,
        verbose_name="Encrypted Webservice Username",
        blank=True,
        help_text=_(
            "The encrypted API user's username used to obtain new tokens."
            " It will be encrypted when stored in the database."
        ),
        null=True,
    )

    @property
    def encrypted_username(self):
        """
        Return encrypted username as a string.

        The data is encrypted in the DB at rest, but is unencrypted in the app when retrieved through the
        decrypted_username field. This method will encrypt the username again before sending.
        """
        if self.decrypted_username:
            return force_str(
                self._meta.get_field('decrypted_username').fernet.encrypt(
                    force_bytes(self.decrypted_username)
                )
            )
        return self.decrypted_username

    @encrypted_username.setter
    def encrypted_username(self, value):
        """
        Set the encrypted username.
        """
        self.decrypted_username = value

    decrypted_password = EncryptedCharField(
        max_length=255,
        verbose_name="Encrypted Webservice Password",
        blank=True,
        help_text=_(
            "The encrypted API user's password used to obtain new tokens."
            " It will be encrypted when stored in the database."
        ),
        null=True,
    )

    @property
    def encrypted_password(self):
        """
        Return encrypted password as a string.

        The data is encrypted in the DB at rest, but is unencrypted in the app when retrieved through the
        decrypted_password field. This method will encrypt the password again before sending.
        """
        if self.decrypted_password:
            return force_str(
                self._meta.get_field('decrypted_password').fernet.encrypt(
                    force_bytes(self.decrypted_password)
                )
            )
        return self.decrypted_password

    @encrypted_password.setter
    def encrypted_password(self, value):
        """
        Set the encrypted password.
        """
        self.decrypted_password = value

    decrypted_token = EncryptedCharField(
        max_length=255,
        verbose_name="Encrypted Webservice Token",
        blank=True,
        help_text=_(
            "The encrypted API user's token used to obtain new tokens."
            " It will be encrypted when stored in the database."
        ),
        null=True,
    )

    @property
    def encrypted_token(self):
        """
        Return encrypted token as a string.

        The data is encrypted in the DB at rest, but is unencrypted in the app when retrieved through the
        decrypted_token field. This method will encrypt the token again before sending.
        """
        if self.decrypted_token:
            return force_str(
                self._meta.get_field('decrypted_token').fernet.encrypt(
                    force_bytes(self.decrypted_token)
                )
            )
        return self.decrypted_token

    @encrypted_token.setter
    def encrypted_token(self, value):
        """
        Set the encrypted token.
        """
        self.decrypted_token = value

    transmission_chunk_size = models.IntegerField(
        default=1,
        help_text=_("The maximum number of data items to transmit to the integrated channel with each request.")
    )

    grade_scale = models.IntegerField(
        default=100,
        verbose_name="Grade Scale",
        help_text=_("The maximum grade points for the courses. Default: 100")
    )

    grade_assignment_name = models.CharField(
        default="(edX integration) Final Grade",
        max_length=255,
        verbose_name="Grade Assignment Name",
        help_text=_(
            "The name for the grade assigment created for the grade integration."
        )
    )

    enable_incomplete_progress_transmission = models.BooleanField(
        help_text=_("When set to True, the configured customer will receive learner data transmissions, for incomplete"
                    " courses as well"),
        default=False,
    )

    class Meta:
        app_label = 'moodle'

    @property
    def is_valid(self):
        """
        Returns whether or not the configuration is valid and ready to be activated

        Args:
            obj: The instance of MoodleEnterpriseCustomerConfiguration
                being rendered with this admin form.
        """
        missing_items = {'missing': []}
        incorrect_items = {'incorrect': []}
        if not self.moodle_base_url:
            missing_items.get('missing').append('moodle_base_url')
        if not self.decrypted_token and not (self.decrypted_username and self.decrypted_password):
            missing_items.get('missing').append('token OR username and password')
        if not self.service_short_name:
            missing_items.get('missing').append('service_short_name')
        if not is_valid_url(self.moodle_base_url):
            incorrect_items.get('incorrect').append('moodle_base_url')
        if len(self.display_name) > 20:
            incorrect_items.get('incorrect').append('display_name')
        return missing_items, incorrect_items

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


class MoodleLearnerDataTransmissionAudit(LearnerDataTransmissionAudit):
    """
    The payload we send to Moodle at a given point in time for an enterprise course enrollment.

    """
    moodle_user_email = models.EmailField(
        max_length=255,
        blank=False,
        null=False,
        help_text='The learner`s Moodle email. This must match the email on edX'
    )

    moodle_completed_timestamp = models.CharField(
        null=True,
        blank=True,
        max_length=10,
        help_text=(
            'Represents the Moodle representation of a timestamp: yyyy-mm-dd, '
            'which is always 10 characters. Can be left unset for audit transmissions.'
        )
    )

    class Meta:
        app_label = 'moodle'
        constraints = [
            models.UniqueConstraint(
                fields=['enterprise_course_enrollment_id', 'course_id'],
                name='moodle_unique_enrollment_course_id'
            )
        ]
        index_together = ['enterprise_customer_uuid', 'plugin_configuration_id']

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

    def serialize(self, *args, **kwargs):
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
        return {
            'userID': self.moodle_user_email,
            'courseID': self.course_id,
            'courseCompleted': 'true' if self.course_completed else 'false',
            'completedTimestamp': self.moodle_completed_timestamp,
            'grade': self.grade,
            'totalHours': self.total_hours,
        }
