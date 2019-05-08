# -*- coding: utf-8 -*-
"""
Client for connecting to Cornerstone.
"""

from __future__ import absolute_import, unicode_literals

import datetime

import requests
from six.moves.urllib.parse import urljoin  # pylint: disable=import-error

from django.apps import apps

from integrated_channels.integrated_channel.client import IntegratedChannelApiClient


class CornerstoneAPIClient(IntegratedChannelApiClient):
    """
    Client for connecting to Cornerstone.

    Specifically, this class supports obtaining access tokens
    and posting user's proogres to completion status endpoints.
    """

    COMPLETION_PROVIDER_SCOPE = 'provider_completion'
    SESSION_TIMEOUT = 60

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
        pass

    def update_content_metadata(self, serialized_data):
        """
        Update content metadata using the Cornerstone course content API.
        Since Cornerstone is following pull content model we don't need to implement this method
        """
        pass

    def delete_content_metadata(self, serialized_data):
        """
        Delete content metadata using the Cornerstone course content API.
        Since Cornerstone is following pull content model we don't need to implement this method
        """
        pass

    def delete_course_completion(self, user_id, payload):  # pylint: disable=unused-argument
        """
        Delete a completion status previously sent to the Cornerstone Completion Status endpoint
        Cornerstone does not support this.
        """
        pass

    def create_course_completion(self, user_id, payload):  # pylint: disable=unused-argument
        """
        Send a completion status payload to the Cornerstone Completion Status endpoint

        Raises:
            HTTPError: if we received a failure response code from Cornerstone
        """
        return self._post(
            urljoin(
                self.enterprise_configuration.cornerstone_base_url,
                self.global_cornerstone_config.completion_status_api_path
            ),
            payload,
            self.COMPLETION_PROVIDER_SCOPE
        )

    def _post(self, url, data, scope):
        """
        Make a POST request using the session object to a Cornerstone endpoint.

        Args:
            url (str): The url to send a POST request to.
            data (str): The json encoded payload to POST.
            scope (str): Must be one of the scopes Cornerstone expects:
                        - `COMPLETION_PROVIDER_SCOPE`
        """
        self._create_session(scope)
        response = self.session.post(url, data=data)
        return response.status_code, response.text

    def _create_session(self, scope):   # pylint: disable=unused-argument
        """
        Instantiate a new session object for use in connecting with Cornerstone
        """
        now = datetime.datetime.utcnow()
        if self.session is None or self.expires_at is None or now >= self.expires_at:
            # Create a new session with a valid token
            if self.session:
                self.session.close()
            # TODO: logic to get oauth access token needs to be implemented here
            oauth_access_token, expires_at = None, None
            session = requests.Session()
            session.timeout = self.SESSION_TIMEOUT
            session.headers['Authorization'] = 'Bearer {}'.format(oauth_access_token)
            session.headers['content-type'] = 'application/json'
            self.session = session
            self.expires_at = expires_at
