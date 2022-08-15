"""
Client for connecting to Cornerstone.
"""

import base64
import json
import logging

import requests

from django.apps import apps

from integrated_channels.cornerstone.utils import get_or_create_key_pair
from integrated_channels.integrated_channel.client import IntegratedChannelApiClient
from integrated_channels.utils import generate_formatted_log

LOGGER = logging.getLogger(__name__)


class CornerstoneAPIClient(IntegratedChannelApiClient):
    """
    Client for connecting to Cornerstone.

    Specifically, this class supports obtaining access tokens
    and posting user's course completion status to progress endpoints.
    """

    def __init__(self, enterprise_configuration):
        """
        Instantiate a new client.

        Args:
            enterprise_configuration (CornerstoneEnterpriseCustomerConfiguration): An enterprise customers's
            configuration model for connecting with Cornerstone
        """
        super().__init__(enterprise_configuration)
        self.global_cornerstone_config = apps.get_model('cornerstone', 'CornerstoneGlobalConfiguration').current()
        self.session = None
        self.expires_at = None

    def create_content_metadata(self, serialized_data):
        """
        Create content metadata using the Cornerstone course content API.
        Since Cornerstone is following pull content model we don't need to implement this method
        """
        return 200, ''

    def update_content_metadata(self, serialized_data):
        """
        Update content metadata using the Cornerstone course content API.
        Since Cornerstone is following pull content model we don't need to implement this method
        """
        return 200, ''

    def delete_content_metadata(self, serialized_data):
        """
        Delete content metadata using the Cornerstone course content API.
        Since Cornerstone is following pull content model we don't need to implement this method
        """
        return 200, ''

    def delete_course_completion(self, user_id, payload):
        """
        Delete a completion status previously sent to the Cornerstone Completion Status endpoint
        Cornerstone does not support this.
        """
        return 200, ''

    def cleanup_duplicate_assignment_records(self, courses):
        """
        Not implemented yet.
        """
        LOGGER.error(
            generate_formatted_log(
                self.enterprise_configuration.channel_code(),
                self.enterprise_configuration.enterprise_customer.uuid,
                None,
                None,
                "Cornerstone integrated channel does not yet support assignment deduplication."
            )
        )

    def create_course_completion(self, user_id, payload):
        """
        Send a completion status payload to the Cornerstone Completion Status endpoint

        Raises:
            HTTPError: if we received a failure response code from Cornerstone
        """
        json_payload = json.loads(payload)
        callback_url = json_payload['data'].pop('callbackUrl')
        session_token = self.enterprise_configuration.session_token
        if not session_token:
            session_token = json_payload['data'].pop('sessionToken')

        # When exporting content metadata, we encode course keys that contain invalid chars or
        # set them to uuids to comply with Cornerstone standards
        course_id = json_payload['data'].get('courseId')
        key_mapping = get_or_create_key_pair(course_id)
        json_payload['data']['courseId'] = key_mapping.external_course_id
        url = '{base_url}{callback_url}{completion_path}?sessionToken={session_token}'.format(
            base_url=self.enterprise_configuration.cornerstone_base_url,
            callback_url=callback_url,
            completion_path=self.global_cornerstone_config.completion_status_api_path,
            session_token=session_token,
        )

        response = requests.post(
            url,
            json=[json_payload['data']],
            headers={
                'Authorization': self.authorization_header,
                'Content-Type': 'application/json'
            }
        )
        return response.status_code, response.text

    def create_assessment_reporting(self, user_id, payload):
        """
        Not implemented yet
        """

    @property
    def authorization_header(self):
        """
        Authorization header for authenticating requests to cornerstone progress API.
        """
        return 'Basic {}'.format(
            base64.b64encode('{key}:{secret}'.format(
                key=self.global_cornerstone_config.key, secret=self.global_cornerstone_config.secret
            ).encode('utf-8')).decode()
        )
