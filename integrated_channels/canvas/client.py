# -*- coding: utf-8 -*-
"""
Client for connecting to Canvas.
"""
import json

import requests
from requests.utils import quote
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
        self.course_create_url = CanvasAPIClient.course_create_endpoint(
            self.enterprise_configuration.canvas_base_url,
            self.enterprise_configuration.canvas_account_id
        )

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

    def create_content_metadata(self, serialized_data):
        self._create_session()

        # step 1: create the course
        status_code, response_text = self._post(self.course_create_url, serialized_data)
        created_course_id = json.loads(response_text)['id']

        # step 2: upload image_url and any other details
        self._update_course_details(created_course_id, serialized_data)

        return status_code, response_text

    def update_content_metadata(self, serialized_data):
        self._create_session()

        integration_id = self._extract_integration_id(serialized_data)
        course_id = self._get_course_id_from_integration_id(integration_id)

        url = CanvasAPIClient.course_update_endpoint(
            self.enterprise_configuration.canvas_base_url,
            course_id,
        )

        return self._put(url, serialized_data)

    def delete_content_metadata(self, serialized_data):
        self._create_session()

        integration_id = self._extract_integration_id(serialized_data)
        course_id = self._get_course_id_from_integration_id(integration_id)

        url = '{}/api/v1/courses/{}'.format(
            self.enterprise_configuration.canvas_base_url,
            course_id,
        )

        return self._delete(url)

    def create_course_completion(self, user_id, payload):  # pylint: disable=unused-argument
        learner_data = json.loads(payload)
        self._create_session()

        # Retrieve the Canvas user ID from the user's edx email (it is assumed that the learner's Edx
        # and Canvas emails will match).
        canvas_user_id = self._search_for_canvas_user_by_email(user_id)

        # With the Canvas user ID, retrieve all courses for the user.
        user_courses = self._get_canvas_user_courses_by_id(canvas_user_id)

        # Find the course who's integration ID matches the learner data course ID
        course_id = None
        for course in user_courses:
            integration_id = course['integration_id']
            if '+'.join(integration_id.split(":")[1].split("+")[:2]) == learner_data['courseID']:
                course_id = course['id']
                break

        if not course_id:
            raise CanvasClientError(
                "Course: {course_id} not found registered in Canvas for Edx learner: {user_id}"
                "/Canvas learner: {canvas_user_id}.".format(
                    course_id=learner_data['courseID'],
                    user_id=learner_data['userID'],
                    canvas_user_id=canvas_user_id
                ))

        # Depending on if the assignment already exists, either retrieve or create it.
        assignment_id = self._handle_canvas_assignment_retrieval(integration_id, course_id)

        # Post a grade for the assignment. This shouldn't create a submission for the user, but still update the grade.
        submission_url = '{base_url}/api/v1/courses/{course_id}/assignments/' \
                         '{assignment_id}/submissions/{user_id}'.format(
                             base_url=self.enterprise_configuration.canvas_base_url,
                             course_id=course_id,
                             assignment_id=assignment_id,
                             user_id=canvas_user_id
                         )

        # The percent grade from the grades api is represented as a decimal
        submission_data = {
            'submission': {
                'posted_grade': learner_data['grade'] * 100
            }
        }
        update_grade_response = self.session.put(submission_url, json=submission_data)
        update_grade_response.raise_for_status()
        return update_grade_response.status_code, update_grade_response.text

    def delete_course_completion(self, user_id, payload):  # pylint: disable=unused-argument
        # Todo: There isn't a great way for users to delete course completion data
        pass

    # Private Methods

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

    def _update_course_details(self, course_id, serialized_data):
        """
        Update a course for image_url (and possibly other settings in future)
        This is used only for settings that are not settable in the initial course creation
        """
        try:
            # there is no way to do this in a single request during create
            # https://canvas.instructure.com/doc/api/all_resources.html#method.courses.update
            content_metadata_item = json.loads(serialized_data.decode('utf-8'))['course']
            if "image_url" in content_metadata_item:
                url = CanvasAPIClient.course_update_endpoint(
                    self.enterprise_configuration.canvas_base_url,
                    course_id,
                )
                self._put(url, json.dumps({
                    'course': {'image_url': content_metadata_item['image_url']}
                }).encode('utf-8'))
        except Exception:  # pylint: disable=broad-except
            # we do not want course image update to cause failures
            pass

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

    def _extract_integration_id(self, data):
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
        url = "{}/api/v1/accounts/{}/courses/?search_term={}".format(
            self.enterprise_configuration.canvas_base_url,
            self.enterprise_configuration.canvas_account_id,
            quote(integration_id),
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

    def _search_for_canvas_user_by_email(self, user_email):
        """
        Helper method to make an api call to Canvas using the user's email as a search term.

        Args:
            user_email (string) : The email associated with both the user's Edx account and Canvas account.
        """
        get_user_id_from_email_url = '{url_base}/api/v1/accounts/{account_id}/users?search_term={email_address}'.format(
            url_base=self.enterprise_configuration.canvas_base_url,
            account_id=self.enterprise_configuration.canvas_account_id,
            email_address=user_email
        )
        rsps = self.session.get(get_user_id_from_email_url)
        rsps.raise_for_status()
        get_users_by_email_response = rsps.json()

        try:
            canvas_user_id = get_users_by_email_response[0]['id']
        except (KeyError, IndexError):
            # Trying to figure out how we should handle errors here- should we catch
            # them in the in the transmitter? Should we return 400 but not raise?
            # If we have multiple course completions to post, a raised exception here without
            # anything else will prevent other transmissions to happen.
            raise CanvasClientError(
                "No Canvas user ID found associated with email: {}".format(user_email)
            )
        return canvas_user_id

    def _get_canvas_user_courses_by_id(self, user_id):
        """Helper method to retrieve all courses that a Canvas user is enrolled in."""
        get_users_courses_url = '{canvas_base_url}/api/v1/users/{canvas_user_id}/courses'.format(
            canvas_base_url=self.enterprise_configuration.canvas_base_url,
            canvas_user_id=user_id
        )
        rsps = self.session.get(get_users_courses_url)
        rsps.raise_for_status()
        return rsps.json()

    def _handle_canvas_assignment_retrieval(self, integration_id, course_id):
        """
        Helper method to handle course assignment creation or retrieval. Canvas requires an assignment
        in order for a user to get a grade, so first check the course for the "final grade"
        assignment. This assignment will have a matching integration id to the currently transmitting
        learner data. If this assignment is not yet created on Canvas, send a post request to do so.

        Args:
            integration_id (str) : the string integration id from the edx course.
            course_id (str) : the Canvas course ID relating to the course which the client is currently
            transmitting learner data to.
        """
        # First, check if the course assignment already exists
        canvas_assignments_url = '{canvas_base_url}/api/v1/courses/{course_id}/assignments'.format(
            canvas_base_url=self.enterprise_configuration.canvas_base_url,
            course_id=course_id
        )
        resp = self.session.get(canvas_assignments_url)
        resp.raise_for_status()
        assignments_resp = resp.json()
        assignment_id = None
        for assignment in assignments_resp:
            try:
                if assignment['integration_id'] == integration_id:
                    assignment_id = assignment['id']
                    break
            except (KeyError, ValueError):
                raise CanvasClientError(
                    "Something went wrong retrieving assignments from Canvas. Got response: {}".format(resp.text)
                )

        # Canvas requires a course assignment for a learner to be assigned a grade.
        # If no assignment has been made yet, create it.
        if not assignment_id:
            assignment_creation_data = {
                'assignment': {
                    'name': '(Edx integration) Final Grade',
                    'submission_types': 'none',
                    'integration_id': integration_id,
                    'published': True,
                    'points_possible': 100
                }
            }
            create_assignment_resp = self.session.post(canvas_assignments_url, json=assignment_creation_data)
            create_assignment_resp.raise_for_status()

            try:
                assignment_id = create_assignment_resp.json()['id']
            except (ValueError, KeyError):
                raise CanvasClientError(
                    "Something went wrong creating an assignment on Canvas. Got response: {}".format(
                        create_assignment_resp.text
                    )
                )
        return assignment_id

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
