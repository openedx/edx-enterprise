# -*- coding: utf-8 -*-
"""
Client for connecting to Degreed.
"""

from __future__ import absolute_import, unicode_literals

import datetime
import time

import requests
from integrated_channels.integrated_channel.client import IntegratedChannelApiClient

from django.apps import apps

from six.moves.urllib.parse import urljoin  # pylint: disable=import-error


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
        super(DegreedAPIClient, self).__init__(enterprise_configuration)
        self.global_degreed_config = apps.get_model('degreed', 'DegreedGlobalConfiguration').current()
        self.session = None
        self.expires_at = None

    def create_course_completion(self, user_id, payload):  # pylint: disable=unused-argument
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
            urljoin(self.global_degreed_config.degreed_base_url, self.global_degreed_config.completion_status_api_path),
            payload,
            self.COMPLETION_PROVIDER_SCOPE
        )

    def delete_course_completion(self, user_id, payload):  # pylint: disable=unused-argument
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
            urljoin(self.global_degreed_config.degreed_base_url, self.global_degreed_config.completion_status_api_path),
            payload,
            self.COMPLETION_PROVIDER_SCOPE
        )

    def create_course_content(self, payload):
        """
        Send courses payload to the Degreed Course Content endpoint.

        Args:
            payload: JSON encoded object containing course import data per Degreed documentation.

        Returns:
            A tuple containing the status code and the body of the response.
        Raises:
            HTTPError: if we received a failure response code from Degreed.
        """
        return self._post(
            urljoin(self.global_degreed_config.degreed_base_url, self.global_degreed_config.course_api_path),
            payload,
            self.CONTENT_PROVIDER_SCOPE
        )

    def delete_course_content(self, payload):
        """
        Delete a course in the upstream Degreed Course Catalog.

        Args:
            payload: JSON encoded object containing the required course data for deletion.

        Returns:
            A tuple containing the status code and the body of the response.
        Raises:
            HTTPError: if we received a failure response code from Degreed.
        """
        return self._delete(
            urljoin(self.global_degreed_config.degreed_base_url, self.global_degreed_config.course_api_path),
            payload,
            self.CONTENT_PROVIDER_SCOPE
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
                self.global_degreed_config.degreed_user_id,
                self.global_degreed_config.degreed_user_password,
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
            RequestException: If an unexpected response format was received that we could not parse.
        """
        response = requests.post(
            urljoin(self.global_degreed_config.degreed_base_url, self.global_degreed_config.oauth_api_path),
            data={
                'grant_type': 'password',
                'username': user_id,
                'password': user_password,
                'scope': scope,
            },
            auth=(client_id, client_secret),
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )

        response.raise_for_status()
        data = response.json()
        try:
            expires_at = data['expires_in'] + int(time.time())
            return data['access_token'], datetime.datetime.utcfromtimestamp(expires_at)
        except KeyError:
            raise requests.RequestException(response=response)
