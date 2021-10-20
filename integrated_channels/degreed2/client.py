# -*- coding: utf-8 -*-
"""
Client for connecting to Degreed2.
"""

import datetime
import logging
import time

import requests
from six.moves.urllib.parse import urljoin

from django.apps import apps

from integrated_channels.exceptions import ClientError
from integrated_channels.integrated_channel.client import IntegratedChannelApiClient
from integrated_channels.utils import refresh_session_if_expired

LOGGER = logging.getLogger(__name__)


class Degreed2APIClient(IntegratedChannelApiClient):
    """
    Client for connecting to Degreed2.

    Specifically, this class supports obtaining access tokens and posting to the courses and
    completion status endpoints.
    """

    CONTENT_WRITE_SCOPE = "content:write"
    ALL_DESIRED_SCOPES = "content:read,content:write,completions:write,completions:read"
    SESSION_TIMEOUT = 60

    def __init__(self, enterprise_configuration):
        """
        Instantiate a new client.

        Args:
            enterprise_configuration (Degreed2EnterpriseCustomerConfiguration): An enterprise customers's
            configuration model for connecting with Degreed
        """
        super().__init__(enterprise_configuration)
        self.session = None
        self.expires_at = None
        app_config = apps.get_app_config('degreed2')
        self.oauth_api_path = app_config.oauth_api_path
        self.courses_api_path = app_config.courses_api_path

    def create_assessment_reporting(self, user_id, payload):
        """
        Not implemented yet.
        """

    def cleanup_duplicate_assignment_records(self, courses):
        """
        Not implemented yet.
        """
        LOGGER.error("Degreed integrated channel does not yet support assignment deduplication.")

    def create_course_completion(self, user_id, payload):
        """
        Not implemented yet
        """

    def delete_course_completion(self, user_id, payload):
        """
        Not implemented yet
        """

    def create_content_metadata(self, serialized_data):
        """
        Create content metadata using the Degreed course content API.

        Args:
            serialized_data: JSON-encoded object containing content metadata.

        Raises:
            ClientError: If Degreed API request fails.
        """
        self._sync_content_metadata(serialized_data, 'post')

    def update_content_metadata(self, serialized_data):
        """
        Update content metadata using the Degreed course content API.

        Args:
            serialized_data: JSON-encoded object containing content metadata.

        Raises:
            ClientError: If Degreed API request fails.
        """
        self._sync_content_metadata(serialized_data, 'patch')

    def delete_content_metadata(self, serialized_data):
        """
        Delete content metadata using the Degreed course content API.

        Args:
            serialized_data: JSON-encoded object containing content metadata.

        Raises:
            ClientError: If Degreed API request fails.
        """
        self._sync_content_metadata(serialized_data, 'delete')

    def _sync_content_metadata(self, serialized_data, http_method):
        """
        Synchronize content metadata using the Degreed course content API.

        Args:
            serialized_data: JSON-encoded object containing content metadata.
            http_method: The HTTP method to use for the API request.

        Raises:
            ClientError: If Degreed API request fails.
        """
        try:
            status_code, response_body = getattr(self, '_' + http_method)(
                urljoin(self.enterprise_configuration.degreed_base_url, self.course_api_path),
                serialized_data,
                self.ALL_DESIRED_SCOPES
            )
        except requests.exceptions.RequestException as exc:
            raise ClientError(
                'Degreed2APIClient request failed: {error} {message}'.format(
                    error=exc.__class__.__name__,
                    message=str(exc)
                )
            ) from exc

        if status_code >= 400:
            raise ClientError(
                'Degreed2APIClient request failed with status {status_code}: {message}'.format(
                    status_code=status_code,
                    message=response_body
                )
            )

    def _post(self, url, data, scope):
        """
        Make a POST request using the session object to a Degreed2 endpoint.

        Args:
            url (str): The url to send a POST request to.
            data (str): The json encoded payload to POST.
            scope (str): Must be one of the scopes Degreed expects:
                        - `CONTENT_WRITE_SCOPE`
                        - `CONTENT_READ_SCOPE`
        """
        self._create_session(scope)
        response = self.session.post(url, data=data)
        return response.status_code, response.text

    def _patch(self, url, data, scope):
        """
        Make a PATCH request using the session object to a Degreed2 endpoint.

        Args:
            url (str): The url to send a POST request to.
            data (str): The json encoded payload to POST.
            scope (str): Must be one of the scopes Degreed expects:
                        - `CONTENT_WRITE_SCOPE`
                        - `CONTENT_READ_SCOPE`
        """
        self._create_session(scope)
        response = self.session.patch(url, data=data)
        return response.status_code, response.text

    def _delete(self, url, data, scope):
        """
        Make a DELETE request using the session object to a Degreed endpoint.

        Args:
            url (str): The url to send a DELETE request to.
            data (str): The json encoded payload to DELETE.
            scope (str): Must be one of the scopes Degreed expects:
                        - `CONTENT_PROVIDER_SCOPE`
                        - `COMPLETION_PROVIDER_SCOPE`
        """
        self._create_session(scope)
        response = self.session.delete(url, data=data)
        return response.status_code, response.text

    def _create_session(self, scope):
        """
        Instantiate a new session object for use in connecting with Degreed
        """
        self.session, self.expires_at = refresh_session_if_expired(
            self._get_oauth_access_token,
            self.session,
            self.expires_at,
        )

    def _get_oauth_access_token(self, scope):
        """ Retrieves OAuth 2.0 access token using the client credentials grant.
        Prefers using the degreed_token_fetch_base_url over the degreed_base_url, if present, to fetch the access token.

        Args:
            scope (str): Must be one or comma separated list of the scopes Degreed expects
        Returns:
            tuple: Tuple containing access token string and expiration datetime.
        Raises:
            HTTPError: If we received a failure response code from Degreed.
            ClientError: If an unexpected response format was received that we could not parse.
        """
        config = self.enterprise_configuration
        base_url = config.degreed_token_fetch_base_url or config.degreed_base_url
        breakpoint()
        response = requests.post(
            urljoin(base_url, self.oauth_api_path),
            data={
                'grant_type': 'client_credentials',
                'scope': scope,
                'client_id': config.client_id,
                'client_secret': config.client_secret,
            },
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )

        try:
            data = response.json()
            expires_at = data['expires_in'] + int(time.time())
            return data['access_token'], datetime.datetime.utcfromtimestamp(expires_at)
        except (KeyError, ValueError) as error:
            raise ClientError(response.text, response.status_code) from error
