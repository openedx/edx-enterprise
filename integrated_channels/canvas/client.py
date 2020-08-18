# -*- coding: utf-8 -*-
"""
Client for connecting to Canvas.
"""
import requests
from six.moves.urllib.parse import urljoin  # pylint: disable=import-error

from django.apps import apps

from integrated_channels.exceptions import ClientError
from integrated_channels.integrated_channel.client import IntegratedChannelApiClient


class CanvasAPIClient(IntegratedChannelApiClient):
    """
    Client for connecting to Canvas.

    Required Canvas auth credentials to instantiate a new client object.
        -  canvas_base_url : the base url of the user's Canvas instance.
        -  client_id : the ID associated with a Canvas developer key.
        -  client_secret : the secret key associated with a Canvas developer key.
        -  refresh_token : the refresh token token retrieved by the `oauth/complete`
        endpoint after the user authorizes the use of their Canvas account.

    Order of Operations:
        Before the client can connect with an Enterprise user's Canvas account, the user will need to
        follow these steps
            - Create a developer key with their Canvas account
            - Provide the ECS team with their developer key's client ID and secret.
            - ECS will return a url for the user to visit which will prompt authorization and redirect when
            the user hits the `confirm` button.
            - The redirect will hit the `oauth/complete` endpoint which will use the passed oauth code
            to request the Canvas oauth refresh token and save it to the Enterprise user's Canvas API config
            - The refresh token is used at client instantiation to request the user's access token, this access
            token is saved to the client's session and is used to make POST and DELETE requests to Canvas.
    """

    def __init__(self, enterprise_configuration):
        """
        Instantiate a new client.

        Args:
            enterprise_configuration (CanvasEnterpriseCustomerConfiguration): An enterprise customers's
            configuration model for connecting with Canvas
        """
        super(CanvasAPIClient, self).__init__(enterprise_configuration)
        self.config = apps.get_app_config('canvas')
        self.session = None
        self.expires_at = None

    def create_course_completion(self, user_id, payload):  # pylint: disable=unused-argument
        pass

    def delete_course_completion(self, user_id, payload):  # pylint: disable=unused-argument
        pass

    def create_content_metadata(self, serialized_data):
        url = '{}/api/v1/accounts/{}/courses'.format(
            self.enterprise_configuration.canvas_base_url,
            self.enterprise_configuration.canvas_account_id,
        )
        self._post(url, serialized_data)

    def update_content_metadata(self, serialized_data):
        # Cannot update yet since we don't have course id
        pass

    def delete_content_metadata(self, serialized_data):
        # Cannot delete yet since we don't have course id
        pass

    def _post(self, url, data):
        """
        Make a POST request using the session object to a Canvas endpoint.

        Args:
            url (str): The url to send a POST request to.
            data (str): The json encoded payload to POST.
        """
        self._create_session()
        response = self.session.post(url, data=data)
        return response.status_code, response.text

    def _delete(self, url, data):
        """
        Make a DELETE request using the session object to a Canvas endpoint.

        Args:
            url (str): The url to send a DELETE request to.
            data (str): The json encoded payload to DELETE.
        """
        self._create_session()
        response = self.session.delete(url, data=data)
        return response.status_code, response.text

    def _create_session(self):
        """
        Instantiate a new session object for use in connecting with Canvas. Each enterprise customer
        connecting to Canvas should have a single client session.
        """
        if self.session:
            self.session.close()
        # Create a new session with a valid token
        oauth_access_token = self._get_oauth_access_token(
            self.enterprise_configuration.client_id,
            self.enterprise_configuration.client_secret,
        )
        session = requests.Session()
        session.headers['Authorization'] = 'Bearer {}'.format(oauth_access_token)
        session.headers['content-type'] = 'application/json'
        self.session = session

    def _get_oauth_access_token(self, client_id, client_secret):
        """Uses the client id, secret and refresh token to request the user's auth token from Canvas.

        Args:
            client_id (str): API client ID
            client_secret (str): API client secret

        Returns:
            access_token (str): the OAuth access token to access the Canvas API as the user
        Raises:
            HTTPError: If we received a failure response code from Canvas.
            RequestException: If an unexpected response format was received that we could not parse.
        """
        if not client_id:
            raise ClientError("Failed to generate oauth access token: Client ID required.")
        if not client_secret:
            raise ClientError("Failed to generate oauth access token: Client secret required.")
        if not self.enterprise_configuration.refresh_token:
            raise ClientError("Failed to generate oauth access token: Refresh token required.")

        if not self.enterprise_configuration.canvas_base_url or not self.config.oauth_token_auth_path:
            raise ClientError("Failed to generate oauth access token: Canvas oauth path missing from configuration.")
        auth_token_url = urljoin(
            self.enterprise_configuration.canvas_base_url,
            self.config.oauth_token_auth_path,
        )

        auth_token_params = {
            'grant_type': 'refresh_token',
            'client_id': client_id,
            'client_secret': client_secret,
            'state': str(self.enterprise_configuration.enterprise_customer.uuid),
            'refresh_token': self.enterprise_configuration.refresh_token,
        }

        auth_response = requests.post(auth_token_url, auth_token_params)
        auth_response.raise_for_status()
        try:
            data = auth_response.json()
            return data['access_token']
        except (KeyError, ValueError):
            raise requests.RequestException(response=auth_response)
