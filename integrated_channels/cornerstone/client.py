# -*- coding: utf-8 -*-
"""
Client for connecting to Cornerstone.
"""

from __future__ import absolute_import, unicode_literals

import base64
import json

import requests

from django.apps import apps

from integrated_channels.integrated_channel.client import IntegratedChannelApiClient


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
        super(CornerstoneAPIClient, self).__init__(enterprise_configuration)
        self.global_cornerstone_config = apps.get_model('cornerstone', 'CornerstoneGlobalConfiguration').current()
        self.session = None
        self.expires_at = None

    def create_content_metadata(self, serialized_data):
        """
        Create content metadata using the Cornerstone course content API.
        Since Cornerstone is following pull content model we don't need to implement this method
        """

    def update_content_metadata(self, serialized_data):
        """
        Update content metadata using the Cornerstone course content API.
        Since Cornerstone is following pull content model we don't need to implement this method
        """

    def delete_content_metadata(self, serialized_data):
        """
        Delete content metadata using the Cornerstone course content API.
        Since Cornerstone is following pull content model we don't need to implement this method
        """

    def delete_course_completion(self, user_id, payload):  # pylint: disable=unused-argument
        """
        Delete a completion status previously sent to the Cornerstone Completion Status endpoint
        Cornerstone does not support this.
        """

    def create_course_completion(self, user_id, payload):  # pylint: disable=unused-argument
        """
        Send a completion status payload to the Cornerstone Completion Status endpoint

        Raises:
            HTTPError: if we received a failure response code from Cornerstone
        """
        json_payload = json.loads(payload)
        callback_url = json_payload['data'].pop('callbackUrl')
        session_token = json_payload['data'].pop('sessionToken')
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

    @property
    def authorization_header(self):
        """
        Authorization header for authenticating requests to cornerstone progress API.
        """
        return 'Basic {}'.format(
            base64.b64encode(u'{key}:{secret}'.format(
                key=self.global_cornerstone_config.key, secret=self.global_cornerstone_config.secret
            ).encode('utf-8')).decode()
        )
