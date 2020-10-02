# -*- coding: utf-8 -*-
"""
Client for connecting to Blackboard.
"""
import base64
from datetime import datetime, timedelta
from http import HTTPStatus

import requests
from six.moves.urllib.parse import urljoin  # pylint: disable=import-error

from django.apps import apps

from integrated_channels.exceptions import ClientError
from integrated_channels.integrated_channel.client import IntegratedChannelApiClient

# TODO: Refactor candidate (duplication with canvas client)


class BlackboardAPIClient(IntegratedChannelApiClient):
    """
    Client for connecting to Blackboard.
    TODO: Full implementation.
    """

    def __init__(self, enterprise_configuration):
        """
        Instantiate a new client.

        Args:
            enterprise_configuration (BlackboardEnterpriseCustomerConfiguration): An enterprise customers's
            configuration model for connecting with Blackboard
        """
        super(BlackboardAPIClient, self).__init__(enterprise_configuration)
        self.config = apps.get_app_config('blackboard')
        self.session = None
        self.expires_at = None

    def create_content_metadata(self, serialized_data):
        """TODO"""

    def update_content_metadata(self, serialized_data):
        """TODO"""

    def delete_content_metadata(self, serialized_data):
        """TODO"""

    def create_course_completion(self, user_id, payload):  # pylint: disable=unused-argument
        """TODO"""

    def delete_course_completion(self, user_id, payload):  # pylint: disable=unused-argument
        """TODO"""

    def _create_session(self):
        """
        Will only create a new session if token expiry has been reached
        """
        now = datetime.utcnow()
        if self.session is None or self.expires_at is None or now >= self.expires_at:
            # need new session if session expired, or not initialized
            if self.session:
                self.session.close()

            # Create a new session with a valid token
            oauth_access_token, expires_in = self._get_oauth_access_token()

            session = requests.Session()
            session.headers['Authorization'] = 'Bearer {}'.format(oauth_access_token)
            session.headers['Content-Type'] = 'application/json'
            self.session = session
            # expiry expected after `expires_in` seconds
            if expires_in is not None:
                self.expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

    def _get_oauth_access_token(self):
        """Fetch access token using refresh_token workflow from Blackboard

        Returns:
            access_token (str): the OAuth access token to access the Blackboard server
            expires_in (int): the number of seconds after which token will expire
        Raises:
            HTTPError: If we received a failure response code.
            ClientError: If an unexpected response format was received that we could not parse.
        """

        if not self.enterprise_configuration.refresh_token:
            raise ClientError(
                "Failed to generate oauth access token: Refresh token required.",
                HTTPStatus.INTERNAL_SERVER_ERROR
            )

        if (not self.enterprise_configuration.blackboard_base_url
                or not self.config.oauth_token_auth_path):
            raise ClientError(
                "Failed to generate oauth access token: oauth path missing from configuration.",
                HTTPStatus.INTERNAL_SERVER_ERROR
            )
        auth_token_url = urljoin(
            self.enterprise_configuration.blackboard_base_url,
            self.config.oauth_token_auth_path,
        )

        auth_token_params = {
            'grant_type': 'refresh_token',
            'refresh_token': self.enterprise_configuration.refresh_token,
        }

        auth_response = requests.post(
            auth_token_url,
            auth_token_params,
            headers={
                'Authorization': self._create_auth_header(),
                'Content-Type': 'application/x-www-form-urlencoded'
            }
        )
        if auth_response.status_code >= 400:
            raise ClientError(auth_response.text, auth_response.status_code)
        try:
            data = auth_response.json()
            # do not forget to save the new refresh token otherwise subsequent requests will fail
            self.enterprise_configuration.refresh_token = data["refresh_token"]
            self.enterprise_configuration.save()
            return data['access_token'], data["expires_in"]
        except (KeyError, ValueError):
            raise ClientError(auth_response.text, auth_response.status_code)

    def _create_auth_header(self):
        """
        auth header in oauth2 token format as required by blackboard doc
        """
        if not self.enterprise_configuration.client_id:
            raise ClientError(
                "Failed to generate oauth access token: Client ID required.",
                HTTPStatus.INTERNAL_SERVER_ERROR
            )
        if not self.enterprise_configuration.client_secret:
            raise ClientError(
                "Failed to generate oauth access token: Client secret required.",
                HTTPStatus.INTERNAL_SERVER_ERROR
            )
        return 'Basic {}'.format(
            base64.b64encode(u'{key}:{secret}'.format(
                key=self.enterprise_configuration.client_id,
                secret=self.enterprise_configuration.client_secret
            ).encode('utf-8')).decode()
        )
