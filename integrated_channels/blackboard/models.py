"""
Database models for Enterprise Integrated Channel Blackboard.
"""

import json
import uuid
from logging import getLogger

from config_models.models import ConfigurationModel
from simple_history.models import HistoricalRecords
from six.moves.urllib.parse import urljoin

from django.conf import settings
from django.db import models

from integrated_channels.blackboard.exporters.content_metadata import BlackboardContentMetadataExporter
from integrated_channels.blackboard.exporters.learner_data import BlackboardLearnerExporter
from integrated_channels.blackboard.transmitters.content_metadata import BlackboardContentMetadataTransmitter
from integrated_channels.blackboard.transmitters.learner_data import BlackboardLearnerTransmitter
from integrated_channels.integrated_channel.models import (
    EnterpriseCustomerPluginConfiguration,
    LearnerDataTransmissionAudit,
)
from integrated_channels.utils import is_valid_url

LOGGER = getLogger(__name__)
LMS_OAUTH_REDIRECT_URL = urljoin(settings.LMS_ROOT_URL, '/blackboard/oauth-complete')


class GlobalConfigurationManager(models.Manager):
    """
    Model manager for :class:`.BlackboardGlobalConfiguration` model.

    Filters out inactive global configurations.
    """

    # This manager filters out some records, hence according to the Django docs it must not be used
    # for related field access. Although False is default value, it still makes sense to set it explicitly
    # https://docs.djangoproject.com/en/1.10/topics/db/managers/#base-managers
    use_for_related_fields = False

    def get_queryset(self):
        """
        Return a new QuerySet object. Filters out inactive Enterprise Customers.
        """
        return super().get_queryset().filter(enabled=True)


class BlackboardGlobalConfiguration(ConfigurationModel):
    """
    The global configuration for integrating with Blackboard.

    .. no_pii:
    """

    app_key = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name="Blackboard Application Key",
        help_text=(
            "The application API key identifying the edX integration application to be used in the API oauth handshake."
        )
    )

    app_secret = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name="API Client Secret or Application Secret",
        help_text=(
            "The application API secret used to make to identify ourselves as the edX integration app to customer "
            "instances. Called Application Secret in Blackboard"
        )
    )

    class Meta:
        app_label = 'blackboard'

    objects = models.Manager()
    active_config = GlobalConfigurationManager()

    def __str__(self):
        """
        Return a human-readable string representation of the object.
        """
        return "<BlackboardGlobalConfiguration with id {id}>".format(id=self.id)

    def __repr__(self):
        """
        Return uniquely identifying string representation.
        """
        return self.__str__()


class BlackboardEnterpriseCustomerConfiguration(EnterpriseCustomerPluginConfiguration):
    """
    The Enterprise-specific configuration we need for integrating with Blackboard.
    """

    client_id = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name="API Client ID or Blackboard Application Key",
        help_text=(
            "The API Client ID provided to edX by the enterprise customer to be used to make API "
            "calls on behalf of the customer. Called Application Key in Blackboard"
        )
    )

    client_secret = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name="API Client Secret or Application Secret",
        help_text=(
            "The API Client Secret provided to edX by the enterprise customer to be used to make "
            " API calls on behalf of the customer. Called Application Secret in Blackboard"
        )
    )

    blackboard_base_url = models.CharField(
        max_length=255,
        blank=True,
        default='',
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

    uuid = models.UUIDField(
        unique=True,
        default=uuid.uuid4,
        editable=False,
        help_text=(
            "A UUID for use in public-facing urls such as oauth state variables."
        )
    )

    history = HistoricalRecords()

    class Meta:
        app_label = 'blackboard'

    @property
    def oauth_authorization_url(self):
        """
        Returns: the oauth authorization url when the blackboard_base_url and client_id are available.

        Args:
            obj: The instance of BlackboardEnterpriseCustomerConfiguration
                being rendered with this admin form.
        """
        if self.blackboard_base_url and self.client_id:
            return (f'{self.blackboard_base_url}/learn/api/public/v1/oauth2/authorizationcode'
                    f'?redirect_uri={LMS_OAUTH_REDIRECT_URL}&'
                    f'scope=read%20write%20delete%20offline&response_type=code&'
                    f'client_id={self.client_id}&state={self.uuid}')
        else:
            return None

    @property
    def is_valid(self):
        """
        Returns whether or not the configuration is valid and ready to be activated

        Args:
            obj: The instance of BlackboardEnterpriseCustomerConfiguration
                being rendered with this admin form.
        """
        missing_items = {'missing': []}
        incorrect_items = {'incorrect': []}
        if not self.blackboard_base_url:
            missing_items.get('missing').append('blackboard_base_url')
        if not self.refresh_token:
            missing_items.get('missing').append('refresh_token')
        if not is_valid_url(self.blackboard_base_url):
            incorrect_items.get('incorrect').append('blackboard_base_url')
        if len(self.display_name) > 20:
            incorrect_items.get('incorrect').append('display_name')
        return missing_items, incorrect_items

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


class BlackboardLearnerAssessmentDataTransmissionAudit(LearnerDataTransmissionAudit):
    """
    The payload correlated to a courses subsection learner data we send to blackboard at a given point in time for an
    enterprise course enrollment.

    .. no_pii:
    """
    blackboard_user_email = models.CharField(
        max_length=255,
        blank=False,
        null=False
    )

    grade_point_score = models.FloatField(
        blank=False,
        null=False,
        help_text="The amount of points that the learner scored on the subsection."
    )

    grade_points_possible = models.FloatField(
        blank=False,
        null=False,
        help_text="The total amount of points that the learner could score on the subsection."
    )

    class Meta:
        app_label = 'blackboard'

    def __str__(self):
        return (
            '<BlackboardLearnerAssessmentDataTransmissionAudit {transmission_id} for enterprise enrollment '
            '{enrollment}, email {blackboard_user_email}, and course {course_id}>'.format(
                transmission_id=self.id,
                enrollment=self.enterprise_course_enrollment_id,
                blackboard_user_email=self.blackboard_user_email,
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
        Convert the audit record's fields into blackboard key/value pairs.
        """
        return dict(
            userID=self.blackboard_user_email,
            courseID=self.course_id,
            grade=self.grade,
            subsectionID=self.subsection_id,
            points_possible=self.grade_points_possible,
            points_earned=self.grade_point_score,
            subsection_name=self.subsection_name,
        )

    @classmethod
    def audit_type(cls):
        """
        Assessment level audit type labeling
        """
        return "assessment"


class BlackboardLearnerDataTransmissionAudit(LearnerDataTransmissionAudit):
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

    blackboard_completed_timestamp = models.CharField(
        null=True,
        blank=True,
        max_length=10,
        help_text=(
            'Represents the Blackboard representation of a timestamp: yyyy-mm-dd, '
            'which is always 10 characters. Can be left unset for audit transmissions.'
        )
    )

    class Meta:
        app_label = 'blackboard'
        index_together = ['enterprise_customer_uuid', 'plugin_configuration_id']

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
        Convert the audit record's fields into Blackboard key/value pairs.
        """
        return dict(
            userID=self.blackboard_user_email,
            courseID=self.course_id,
            courseCompleted="true" if self.course_completed else "false",
            completedTimestamp=self.blackboard_completed_timestamp,
            grade=self.grade,
            totalHours=self.total_hours,
        )
