# -*- coding: utf-8 -*-
"""
Client for connecting to Degreed2.
"""

import json
import logging

import requests
from six.moves.urllib.parse import urljoin

from django.apps import apps

from integrated_channels.exceptions import ClientError
from integrated_channels.integrated_channel.client import IntegratedChannelApiClient
from integrated_channels.utils import generate_formatted_log, refresh_session_if_expired

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
        # to log without having to pass channel_name, ent_customer_uuid each time
        self.make_log_msg = lambda course_key, message, lms_user_id=None: generate_formatted_log(
            'degreed2',
            self.enterprise_configuration.enterprise_customer.uuid,
            lms_user_id,
            course_key,
            message,
        )

    def get_oauth_url(self):
        config = self.enterprise_configuration
        base_url = config.degreed_token_fetch_base_url or config.degreed_base_url
        return urljoin(base_url, self.oauth_api_path)

    def get_courses_url(self):
        return urljoin(self.enterprise_configuration.degreed_base_url, self.courses_api_path)

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
        channel_metadata_item = json.loads(serialized_data.decode('utf-8'))
        # only expect one course in this array as of now (chunk size is 1)
        a_course = channel_metadata_item['courses'][0]
        status_code, response_body = self._sync_content_metadata(a_course, 'post')
        if status_code == 409:
            # course already exists, don't raise failure, but log and move on
            LOGGER.warning(
                self.make_log_msg(
                    a_course.get('external-id'),
                    f'Course with integration_id = {a_course.get("external-id")} already exists, '
                )
            )
        elif status_code >= 400:
            raise ClientError(
                f'Degreed2APIClient create_content_metadata failed with status {status_code}: {response_body}'
            )
        return status_code, response_body

    def update_content_metadata(self, serialized_data):
        """
        Update content metadata using the Degreed course content API.

        Args:
            serialized_data: JSON-encoded object containing content metadata.

        Raises:
            ClientError: If Degreed API request fails.
        """
        channel_metadata_item = json.loads(serialized_data.decode('utf-8'))
        self._sync_content_metadata(channel_metadata_item['courses'][0], 'patch')

    def delete_content_metadata(self, serialized_data):
        """
        Delete content metadata using the Degreed course content API.

        Args:
            serialized_data: JSON-encoded object containing content metadata.

        Raises:
            ClientError: If Degreed API request fails.
        """
        channel_metadata_item = json.loads(serialized_data.decode('utf-8'))
        self._sync_content_metadata(channel_metadata_item['courses'][0], 'delete')

    def _sync_content_metadata(self, json_payload, http_method):
        """
        Synchronize content metadata using the Degreed course content API.

        Args:
            json_payload: JSON object containing content metadata converted into Degreed2 form.
            http_method: The HTTP method to use for the API request.

        Raises:
            ClientError: If Degreed API request fails.
        """
        json_to_send = {
            "data": {
                "type": "content/courses",
                "attributes": json_payload,
            }
        }
        LOGGER.info(f'About to post payload: {json_to_send}')
        try:
            status_code, response_body = getattr(self, '_' + http_method)(
                self.get_courses_url(),
                json_to_send,
                self.ALL_DESIRED_SCOPES
            )
        except requests.exceptions.RequestException as exc:
            raise ClientError(
                'Degreed2APIClient request failed: {error} {message}'.format(
                    error=exc.__class__.__name__,
                    message=str(exc)
                )
            ) from exc
        return status_code, response_body

    def _post(self, url, data, scope):
        """
        Make a POST request using the session object to a Degreed2 endpoint.

        Args:
            url (str): The url to send a POST request to.
            data (str): The json payload to POST.
            scope (str): Must be one of the scopes Degreed expects:
                        - `CONTENT_WRITE_SCOPE`
                        - `CONTENT_READ_SCOPE`
        """
        self._create_session(scope)
        response = self.session.post(url, json=data)
        return response.status_code, response.text

    def _patch(self, url, data, scope):
        """
        Make a PATCH request using the session object to a Degreed2 endpoint.

        Args:
            url (str): The url to send a POST request to.
            data (str): The json payload to POST.
            scope (str): Must be one of the scopes Degreed expects:
                        - `CONTENT_WRITE_SCOPE`
                        - `CONTENT_READ_SCOPE`
        """
        self._create_session(scope)
        response = self.session.patch(url, json=data)
        return response.status_code, response.text

    def _delete(self, url, data, scope):
        """
        Make a DELETE request using the session object to a Degreed endpoint.

        Args:
            url (str): The url to send a DELETE request to.
            data (str): The json payload to DELETE.
            scope (str): Must be one of the scopes Degreed expects:
                        - `CONTENT_PROVIDER_SCOPE`
                        - `COMPLETION_PROVIDER_SCOPE`
        """
        self._create_session(scope)
        response = self.session.delete(url, json=data)
        return response.status_code, response.text

    def _create_session(self, scope):
        """
        Instantiate a new session object for use in connecting with Degreed
        """
        self.session, self.expires_at = refresh_session_if_expired(
            lambda: self._get_oauth_access_token(scope),
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
        response = requests.post(
            self.get_oauth_url(),
            data={
                'grant_type': 'client_credentials',
                'scope': scope,
                'client_id': config.key,
                'client_secret': config.secret,
            },
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )

        try:
            data = response.json()
            return data['access_token'], data['expires_in']
        except (KeyError, ValueError) as error:
            raise ClientError(response.text, response.status_code) from error
