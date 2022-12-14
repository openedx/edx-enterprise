"""
Database models for Enterprise Integrated Channel Canvas.
"""

import json
import uuid
from logging import getLogger

from simple_history.models import HistoricalRecords
from six.moves.urllib.parse import urljoin

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from integrated_channels.canvas.exporters.content_metadata import CanvasContentMetadataExporter
from integrated_channels.canvas.exporters.learner_data import CanvasLearnerExporter
from integrated_channels.canvas.transmitters.content_metadata import CanvasContentMetadataTransmitter
from integrated_channels.canvas.transmitters.learner_data import CanvasLearnerTransmitter
from integrated_channels.integrated_channel.models import (
    EnterpriseCustomerPluginConfiguration,
    LearnerDataTransmissionAudit,
)
from integrated_channels.utils import is_valid_url

LOGGER = getLogger(__name__)
LMS_OAUTH_REDIRECT_URL = urljoin(settings.LMS_ROOT_URL, '/canvas/oauth-complete')


class CanvasEnterpriseCustomerConfiguration(EnterpriseCustomerPluginConfiguration):
    """
    The Enterprise-specific configuration we need for integrating with Canvas.

    Based on: https://canvas.instructure.com/doc/api/file.oauth.html#oauth2-flow-3
    """

    client_id = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name="API Client ID",
        help_text=_(
            "The API Client ID provided to edX by the enterprise customer to be used to make API "
            "calls to Canvas on behalf of the customer."
        )
    )

    client_secret = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name="API Client Secret",
        help_text=_(
            "The API Client Secret provided to edX by the enterprise customer to be used to make "
            " API calls to Canvas on behalf of the customer."
        )
    )

    canvas_account_id = models.BigIntegerField(
        null=True,
        blank=True,
        verbose_name="Canvas Account Number",
        help_text=_("Account number to use during api calls. Called account_id in canvas. "
                    " Required to create courses etc.")
    )

    canvas_base_url = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name="Canvas Base URL",
        help_text=_("The base URL used for API requests to Canvas, i.e. https://instructure.com.")
    )

    refresh_token = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Oauth2 Refresh Token",
        help_text=_("The refresh token provided by Canvas along with the access token request, used to "
                    "re-request the access tokens over multiple client sessions.")
    )

    # overriding base model field, to use chunk size 1 default
    transmission_chunk_size = models.IntegerField(
        default=1,
        help_text=_("The maximum number of data items to transmit to the integrated channel "
                    "with each request.")
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
        app_label = 'canvas'

    @property
    def oauth_authorization_url(self):
        """
        Returns: the oauth authorization url when the canvas_base_url and client_id are available.

        Args:
            obj: The instance of CanvasEnterpriseCustomerConfiguration
                being rendered with this admin form.
        """
        if self.canvas_base_url and self.client_id:
            return (f'{self.canvas_base_url}/login/oauth2/auth'
                    f'?redirect_uri={LMS_OAUTH_REDIRECT_URL}&'
                    f'response_type=code&'
                    f'client_id={self.client_id}&state={self.uuid}')
        else:
            return None

    @property
    def is_valid(self):
        """
        Returns whether or not the configuration is valid and ready to be activated

        Args:
            obj: The instance of CanvasEnterpriseCustomerConfiguration
                being rendered with this admin form.
        """
        missing_items = {'missing': []}
        incorrect_items = {'incorrect': []}
        if not self.client_id:
            missing_items.get('missing').append('client_id')
        if not self.client_secret:
            missing_items.get('missing').append('client_secret')
        if not self.canvas_base_url:
            missing_items.get('missing').append('canvas_base_url')
        if not self.canvas_account_id:
            missing_items.get('missing').append('canvas_account_id')
        if not self.refresh_token:
            missing_items.get('missing').append('refresh_token')
        if not is_valid_url(self.canvas_base_url):
            incorrect_items.get('incorrect').append('canvas_base_url')
        if len(self.display_name) > 30:
            incorrect_items.get('incorrect').append('display_name')
        return missing_items, incorrect_items

    def __str__(self):
        """
        Return human-readable string representation.
        """
        return "<CanvasEnterpriseCustomerConfiguration for Enterprise {enterprise_name}>".format(
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
        return 'CANVAS'

    def get_learner_data_transmitter(self):
        return CanvasLearnerTransmitter(self)

    def get_learner_data_exporter(self, user):
        return CanvasLearnerExporter(user, self)

    def get_content_metadata_exporter(self, user):
        return CanvasContentMetadataExporter(user, self)

    def get_content_metadata_transmitter(self):
        return CanvasContentMetadataTransmitter(self)


class CanvasLearnerAssessmentDataTransmissionAudit(LearnerDataTransmissionAudit):
    """
    The payload correlated to a courses subsection learner data we send to canvas at a given point in time for an
    enterprise course enrollment.

    .. no_pii:
    """
    canvas_user_email = models.CharField(
        max_length=255,
        blank=False,
        null=False
    )

    grade_point_score = models.FloatField(
        blank=False,
        null=False,
        help_text=_("The amount of points that the learner scored on the subsection.")
    )

    grade_points_possible = models.FloatField(
        blank=False,
        null=False,
        help_text=_("The total amount of points that the learner could score on the subsection.")
    )

    class Meta:
        app_label = 'canvas'

    def __str__(self):
        return (
            '<CanvasLearnerAssessmentDataTransmissionAudit {transmission_id} for enterprise enrollment {enrollment}, '
            'email {canvas_user_email}, and course {course_id}>'.format(
                transmission_id=self.id,
                enrollment=self.enterprise_course_enrollment_id,
                canvas_user_email=self.canvas_user_email,
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
        Convert the audit record's fields into Canvas key/value pairs.
        """
        return dict(
            userID=self.canvas_user_email,
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


class CanvasLearnerDataTransmissionAudit(LearnerDataTransmissionAudit):
    """
    The payload we send to canvas at a given point in time for an enterprise course enrollment.

    .. no_pii:
    """
    canvas_user_email = models.CharField(
        max_length=255,
        blank=False,
        null=False
    )

    canvas_completed_timestamp = models.CharField(
        null=True,
        blank=True,
        max_length=10,
        help_text=_(
            'Represents the canvas representation of a timestamp: yyyy-mm-dd, '
            'which is always 10 characters. Can be left unset for audit transmissions.'
        )
    )

    # XXX non-standard
    grade = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        app_label = 'canvas'

    def __str__(self):
        return (
            '<CanvasLearnerDataTransmissionAudit {transmission_id} for enterprise enrollment {enrollment}, '
            'email {canvas_user_email}, and course {course_id}>'.format(
                transmission_id=self.id,
                enrollment=self.enterprise_course_enrollment_id,
                canvas_user_email=self.canvas_user_email,
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
        Convert the audit record's fields into Canvas key/value pairs.
        """
        return dict(
            userID=self.canvas_user_email,
            courseID=self.course_id,
            courseCompleted="true" if self.course_completed else "false",
            completedTimestamp=self.canvas_completed_timestamp,
            grade=self.grade,
        )
