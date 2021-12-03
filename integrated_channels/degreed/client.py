# -*- coding: utf-8 -*-
"""
Client for connecting to Degreed.
"""

import datetime
import logging
import time

import requests
from six.moves.urllib.parse import urljoin

from django.apps import apps

from integrated_channels.exceptions import ClientError
from integrated_channels.integrated_channel.client import IntegratedChannelApiClient
from integrated_channels.utils import generate_formatted_log

LOGGER = logging.getLogger(__name__)


class DegreedAPIClient(IntegratedChannelApiClient):
    """
    Client for connecting to Degreed.

    Specifically, this class supports obtaining access tokens and posting to the courses and
    completion status endpoints.
    """

    CONTENT_PROVIDER_SCOPE = 'provider_content'
    COMPLETION_PROVIDER_SCOPE = 'provider_completion'
    SESSION_TIMEOUT = 60

    def __init__(self, enterprise_configuration):
        """
        Instantiate a new client.

        Args:
            enterprise_configuration (DegreedEnterpriseCustomerConfiguration): An enterprise customers's
            configuration model for connecting with Degreed
        """
        super().__init__(enterprise_configuration)
        self.global_degreed_config = apps.get_model('degreed', 'DegreedGlobalConfiguration').current()
        self.session = None
        self.expires_at = None

    def create_assessment_reporting(self, user_id, payload):
        """
        Not implemented yet.
        """
        LOGGER.error(
            generate_formatted_log(
                self.enterprise_configuration.channel_code(),
                self.enterprise_configuration.enterprise_customer.uuid,
                None,
                None,
                "Degreed integrated channel does not yet support assessment reporting."
            )
        )

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
                "Degreed integrated channel does not yet support assignment deduplication."
            )
        )

    def create_course_completion(self, user_id, payload):
        """
        Send a completion status payload to the Degreed Completion Status endpoint

        Args:
            user_id: Unused.
            payload: JSON encoded object (serialized from DegreedLearnerDataTransmissionAudit)
                containing completion status fields per Degreed documentation.

        Returns:
            A tuple containing the status code and the body of the response.
        Raises:
            HTTPError: if we received a failure response code from Degreed
        """
        return self._post(
            urljoin(
                self.enterprise_configuration.degreed_base_url,
                self.global_degreed_config.completion_status_api_path
            ),
            payload,
            self.COMPLETION_PROVIDER_SCOPE
        )

    def delete_course_completion(self, user_id, payload):
        """
        Delete a completion status previously sent to the Degreed Completion Status endpoint

        Args:
            user_id: Unused.
            payload: JSON encoded object (serialized from DegreedLearnerDataTransmissionAudit)
                containing the required completion status fields for deletion per Degreed documentation.

        Returns:
            A tuple containing the status code and the body of the response.
        Raises:
            HTTPError: if we received a failure response code from Degreed
        """
        return self._delete(
            urljoin(
                self.enterprise_configuration.degreed_base_url,
                self.global_degreed_config.completion_status_api_path
            ),
            payload,
            self.COMPLETION_PROVIDER_SCOPE
        )

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
        self._sync_content_metadata(serialized_data, 'post')

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
                urljoin(self.enterprise_configuration.degreed_base_url, self.global_degreed_config.course_api_path),
                serialized_data,
                self.CONTENT_PROVIDER_SCOPE
            )
        except requests.exceptions.RequestException as exc:
            raise ClientError(
                'DegreedAPIClient request failed: {error} {message}'.format(
                    error=exc.__class__.__name__,
                    message=str(exc)
                )
            ) from exc

        if status_code >= 400:
            raise ClientError(
                'DegreedAPIClient request failed with status {status_code}: {message}'.format(
                    status_code=status_code,
                    message=response_body
                )
            )

    def _post(self, url, data, scope):
        """
        Make a POST request using the session object to a Degreed endpoint.

        Args:
            url (str): The url to send a POST request to.
            data (str): The json encoded payload to POST.
            scope (str): Must be one of the scopes Degreed expects:
                        - `CONTENT_PROVIDER_SCOPE`
                        - `COMPLETION_PROVIDER_SCOPE`
        """
        self._create_session(scope)
        response = self.session.post(url, data=data)
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
        now = datetime.datetime.utcnow()
        if self.session is None or self.expires_at is None or now >= self.expires_at:
            # Create a new session with a valid token
            if self.session:
                self.session.close()
            oauth_access_token, expires_at = self._get_oauth_access_token(
                self.enterprise_configuration.key,
                self.enterprise_configuration.secret,
                self.enterprise_configuration.degreed_user_id,
                self.enterprise_configuration.degreed_user_password,
                scope
            )
            session = requests.Session()
            session.timeout = self.SESSION_TIMEOUT
            session.headers['Authorization'] = 'Bearer {}'.format(oauth_access_token)
            session.headers['content-type'] = 'application/json'
            self.session = session
            self.expires_at = expires_at

    def _get_oauth_access_token(self, client_id, client_secret, user_id, user_password, scope):
        """ Retrieves OAuth 2.0 access token using the client credentials grant.

        Args:
            client_id (str): API client ID
            client_secret (str): API client secret
            user_id (str): Degreed company ID
            user_password (str): Degreed user password
            scope (str): Must be one of the scopes Degreed expects:
                        - `CONTENT_PROVIDER_SCOPE`
                        - `COMPLETION_PROVIDER_SCOPE`

        Returns:
            tuple: Tuple containing access token string and expiration datetime.
        Raises:
            HTTPError: If we received a failure response code from Degreed.
            ClientError: If an unexpected response format was received that we could not parse.
        """
        response = requests.post(
            urljoin(self.enterprise_configuration.degreed_base_url, self.global_degreed_config.oauth_api_path),
            data={
                'grant_type': 'password',
                'username': user_id,
                'password': user_password,
                'scope': scope,
            },
            auth=(client_id, client_secret),
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )

        try:
            data = response.json()
            expires_at = data['expires_in'] + int(time.time())
            return data['access_token'], datetime.datetime.utcfromtimestamp(expires_at)
        except (KeyError, ValueError) as error:
            raise ClientError(response.text, response.status_code) from error
