# -*- coding: utf-8 -*-
"""
Client for connecting to Canvas.
"""
import json

import requests
from six.moves.urllib.parse import urljoin  # pylint: disable=import-error

from django.apps import apps

from integrated_channels.exceptions import CanvasClientError, ClientError
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

    @staticmethod
    def course_create_endpoint(canvas_base_url, canvas_account_id):
        """
        Returns endpoint to POST to for course creation
        """
        return '{}/api/v1/accounts/{}/courses'.format(
            canvas_base_url,
            canvas_account_id,
        )

    @staticmethod
    def course_update_endpoint(canvas_base_url, course_id):
        """
        Returns endpoint to PUT to for course update
        """
        return '{}/api/v1/courses/{}'.format(
            canvas_base_url,
            course_id,
        )

    def create_course_completion(self, user_id, payload):  # pylint: disable=unused-argument
        pass

    def delete_course_completion(self, user_id, payload):  # pylint: disable=unused-argument
        pass

    def create_content_metadata(self, serialized_data):
        self._create_session()

        # step 1: create the course
        url = CanvasAPIClient.course_create_endpoint(
            self.enterprise_configuration.canvas_base_url,
            self.enterprise_configuration.canvas_account_id
        )
        status_code, response_text = self._post(url, serialized_data)

        # step 2: upload image_url if present
        try:
            # there is no way to do this in a single request during create
            # https://canvas.instructure.com/doc/api/all_resources.html#method.courses.update
            created_course_id = json.loads(response_text)['id']
            content_metadata = json.loads(serialized_data.decode('utf-8'))['course']
            if "image_url" in content_metadata:
                url = CanvasAPIClient.course_update_endpoint(
                    self.enterprise_configuration.canvas_base_url,
                    created_course_id,
                )
                self._put(url, json.dumps({
                    'course': {'image_url': content_metadata['image_url']}
                }).encode('utf-8'))
        except Exception:  # pylint: disable=broad-except
            # we do not want course image update to cause failures
            pass

        return status_code, response_text

    def update_content_metadata(self, serialized_data):
        self._create_session()

        integration_id = self._get_integration_id_from_transmition_data(serialized_data)
        course_id = self._get_course_id_from_integration_id(integration_id)

        url = CanvasAPIClient.course_update_endpoint(
            self.enterprise_configuration.canvas_base_url,
            course_id,
        )

        return self._put(url, serialized_data)

    def delete_content_metadata(self, serialized_data):
        self._create_session()

        integration_id = self._get_integration_id_from_transmition_data(serialized_data)
        course_id = self._get_course_id_from_integration_id(integration_id)

        url = '{}/api/v1/courses/{}'.format(
            self.enterprise_configuration.canvas_base_url,
            course_id,
        )

        return self._delete(url)

    def _post(self, url, data):
        """
        Make a POST request using the session object to a Canvas endpoint.

        Args:
            url (str): The url to send a POST request to.
            data (bytearray): The json encoded payload to POST.
        """
        post_response = self.session.post(url, data=data)
        post_response.raise_for_status()
        return post_response.status_code, post_response.text

    def _put(self, url, data):
        """
        Make a PUT request using the session object to the Canvas course update endpoint

        Args:
            url (str): The canvas url to send update requests to.
            data (bytearray): The json encoded payload to UPDATE. This also contains the integration
            ID used to match a course with a course ID.
        """
        put_response = self.session.put(url, data=data)
        put_response.raise_for_status()
        return put_response.status_code, put_response.text

    def _delete(self, url):
        """
        Make a DELETE request using the session object to the Canvas course delete endpoint.

        Args:
            url (str): The canvas url to send delete requests to.
        """
        delete_response = self.session.delete(url, data='{"event":"delete"}')
        delete_response.raise_for_status()

        return delete_response.status_code, delete_response.text

    def _get_integration_id_from_transmition_data(self, data):
        """
        Retrieve the integration ID string from the encoded transmission data and apply appropriate
        error handling.

        Args:
            data (bytearray): The json encoded payload intended for a Canvas endpoint.
        """
        if not data:
            raise CanvasClientError("No data to transmit.")
        try:
            integration_id = json.loads(
                data.decode("utf-8")
            )['course']['integration_id']
        except KeyError:
            raise CanvasClientError("Could not transmit data, no integration ID present.")
        except AttributeError:
            raise CanvasClientError("Unable to decode data.")

        return integration_id

    def _get_course_id_from_integration_id(self, integration_id):
        """
        To obtain course ID we have to request all courses associated with the integrated
        account and match the one with our integration ID.

        Args:
            integration_id (string): The ID retrieved from the transmission payload.
        """
        url = "{}/api/v1/accounts/{}/courses/".format(
            self.enterprise_configuration.canvas_base_url,
            self.enterprise_configuration.canvas_account_id
        )
        all_courses_response = self.session.get(url).json()
        course_id = None
        for course in all_courses_response:
            if course['integration_id'] == integration_id:
                course_id = course['id']
                break

        if not course_id:
            raise CanvasClientError("No Canvas courses found with associated integration ID: {}.".format(
                integration_id
            ))
        return course_id

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
