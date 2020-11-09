# -*- coding: utf-8 -*-
"""
Client for connecting to Moodle.
"""

import json
from http import HTTPStatus
from urllib.parse import urlencode, urljoin

import requests

from django.apps import apps

from integrated_channels.exceptions import ClientError
from integrated_channels.integrated_channel.client import IntegratedChannelApiClient

MOODLE_FINAL_GRADE_ASSIGNMENT_NAME = '(edX integration) Final Grade'


def moodle_request_wrapper(method):
    """
    Wraps requests to Moodle's API in a token check.
    Will obtain a new token if there isn't one.
    """
    def inner(self, *args, **kwargs):
        if not self.token:
            self.token = self._get_access_token()  # pylint: disable=protected-access
        response = method(self, *args, **kwargs)
        try:
            body = response.json()
        except (AttributeError, ValueError):
            # Moodle spits back an entire HTML page if something is wrong in our URL format.
            # This cannot be converted to JSON thus the above fails miserably.
            # The above can fail with different errors depending on the format of the returned page.
            # Moodle of course does not tell us what is wrong in any part of this HTML.
            raise ClientError('Moodle API task "{method}" failed due to unknown error.'.format(
                method=method.__name__), response.status_code)
        if isinstance(body, list):
            # On course creation (and ONLY course creation) success,
            # Moodle returns a list of JSON objects, because of course it does.
            # Otherwise, it fails instantly and returns actual JSON.
            return response
        if isinstance(body, int):
            # This only happens for grades AFAICT. Zero also doesn't necessarily mean success,
            # but we have nothing else to go on
            if body == 0:
                return 200, ''
            raise ClientError('Moodle API Grade Update failed with int code: {code}'.format(code=body), 500)
        if isinstance(body, str):
            # Grades + debug can sometimes produce lines with debug errors and also "0"
            raise ClientError('Moodle API Grade Update failed with possible error: {body}'.format(body=body), 500)
        error_code = body.get('errorcode')
        warnings = body.get('warnings')
        if error_code and error_code == 'invalidtoken':
            self.token = self._get_access_token()  # pylint: disable=protected-access
            response = method(self, *args, **kwargs)
        elif error_code:
            raise ClientError(
                'Moodle API Client Task "{method}" failed with error code '
                '"{code}" and message: "{msg}" '.format(
                    method=method.__name__, code=error_code, msg=body.get('message'),
                ),
                response.status_code
            )
        elif warnings:
            # More Moodle nonsense!
            errors = []
            for warning in warnings:
                if warning.get('message'):
                    errors.append(warning.get('message'))
            raise ClientError(
                'Moodle API Client Task "{method}" failed with the following error codes: '
                '"{code}"'.format(method=method.__name__, code=errors)
            )
        return response
    return inner


class MoodleAPIClient(IntegratedChannelApiClient):
    """
    Client for connecting to Moodle.
    Transmits learner and course metadata.

    Required configuration to access Moodle:
    - wsusername and wspassword:
        - Web service user and password created in Moodle. Used to generate api tokens.
    - Moodle base url.
        - Customer's Moodle instance url.
        - For local development just `http://localhost` (unless you needed a different port)
    - Moodle service short name.
        - Customer's Moodle service short name
    """

    MOODLE_API_PATH = '/webservice/rest/server.php'

    def __init__(self, enterprise_configuration):
        """
        Instantiate a new client.

        Args:
            enterprise_configuration (MoodleEnterpriseCustomerConfiguration): An enterprise customers's
            configuration model for connecting with Moodle
        """
        super(MoodleAPIClient, self).__init__(enterprise_configuration)
        self.config = apps.get_app_config('moodle')
        self.token = enterprise_configuration.token or self._get_access_token()

    def _post(self, additional_params, method_url=None):
        """
        Compile common params and run request's post function
        """
        params = {
            'wstoken': self.token,
            'moodlewsrestformat': 'json',
        }
        params.update(additional_params)
        if method_url:
            response = requests.post(
                url='{url}&{querystring}'.format(
                    url=method_url,
                    querystring=urlencode(params)
                )
            )
        else:
            response = requests.post(
                url='{url}{api_path}?{querystring}'.format(
                    url=self.enterprise_configuration.moodle_base_url,
                    api_path=self.MOODLE_API_PATH,
                    querystring=urlencode(params)
                )
            )
        return response

    def _get_access_token(self):
        """
        Obtains a new access token from Moodle using username and password.
        """
        querystring = {
            'service': self.enterprise_configuration.service_short_name
        }

        response = requests.post(
            urljoin(
                self.enterprise_configuration.moodle_base_url,
                '/login/token.php',
            ),
            params=querystring,
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            data={
                'username': self.enterprise_configuration.username,
                'password': self.enterprise_configuration.password,
            },
        )

        try:
            data = response.json()
            token = data['token']
            return token
        except (KeyError, ValueError):
            raise ClientError(
                "Failed to post access token. Received message={} from Moodle".format(response.text),
                response.status_code
            )

    @moodle_request_wrapper
    def _get_enrolled_users(self, course_id):
        """
        Helper method to make a request for all user enrollments under a Moodle course ID.
        """
        params = {
            'wstoken': self.token,
            'wsfunction': 'core_enrol_get_enrolled_users',
            'courseid': course_id,
            'moodlewsrestformat': 'json'
        }
        return self._post(params)

    def get_creds_of_user_in_course(self, course_id, user_email):
        """
        Sort through a list of users in a Moodle course and find the ID matching a student's email.
        """
        response = self._get_enrolled_users(course_id)
        parsed_response = response.json()
        user_id = None

        if isinstance(parsed_response, list):
            for enrollment in parsed_response:
                if enrollment.get('email') == user_email:
                    user_id = enrollment.get('id')
                    break
        if not user_id:
            raise ClientError(
                "MoodleAPIClient request failed: 404 User enrollment not found under user={} in course={}.".format(
                    user_email,
                    course_id
                ),
                HTTPStatus.NOT_FOUND.value
            )
        return user_id

    @moodle_request_wrapper
    def _get_course_contents(self, course_id):
        """
        Retrieve the metadata of a Moodle course by ID.
        """
        params = {
            'wstoken': self.token,
            'wsfunction': 'core_course_get_contents',
            'courseid': course_id,
            'moodlewsrestformat': 'json'
        }
        response = requests.get(
            urljoin(
                self.enterprise_configuration.moodle_base_url,
                self.MOODLE_API_PATH,
            ),
            params=params
        )
        return response

    def get_course_final_grade_module(self, course_id):
        """
        Sort through a Moodle course's components for the specific shell assignment designated
        to be the edX integrated Final Grade. This is currently done by module name.

        Returns:
            - course_module_id (int): The ID of the shell assignment
            - module_name (string): The string name of the module. Required for sending a grade update request.
        """
        response = self._get_course_contents(course_id)

        course_module_id = None
        if isinstance(response.json(), list):
            for course in response.json():
                if course.get('name') == 'General':
                    modules = course.get('modules')
                    for module in modules:
                        if module.get('name') == MOODLE_FINAL_GRADE_ASSIGNMENT_NAME:
                            course_module_id = module.get('id')
                            module_name = module.get('modname')

        if not course_module_id:
            raise ClientError(
                'MoodleAPIClient request failed: 404 Completion course module not found in Moodle.'
                ' The enterprise customer needs to create an activity within the course with the name '
                '"(edX integration) Final Grade"',
                HTTPStatus.NOT_FOUND.value
            )
        return course_module_id, module_name

    @moodle_request_wrapper
    def _get_courses(self, key):
        """
        Gets courses from Moodle by key (because we cannot update/delete without it).
        """
        params = {
            'wstoken': self.token,
            'wsfunction': 'core_course_get_courses_by_field',
            'field': 'shortname',
            'value': key,
            'moodlewsrestformat': 'json'
        }
        response = requests.get(
            urljoin(
                self.enterprise_configuration.moodle_base_url,
                self.MOODLE_API_PATH,
            ),
            params=params
        )
        return response

    def get_course_id(self, key):
        """
        Obtain course from Moodle by course key and parse out the id.
        """
        response = self._get_courses(key)
        parsed_response = json.loads(response.text)
        if not parsed_response.get('courses'):
            raise ClientError(
                'MoodleAPIClient request failed: 404 Course key '
                '"{}" not found in Moodle.'.format(key),
                HTTPStatus.NOT_FOUND.value
            )
        return parsed_response['courses'][0]['id']

    @moodle_request_wrapper
    def _wrapped_create_course_completion(self, user_id, payload):
        """
        Wrapped method to request and use Moodle course and user information in order
        to post a final course grade for the user.
        """
        completion_data = json.loads(payload)

        course_id = self.get_course_id(completion_data['courseID'])
        course_module_id, module_name = self.get_course_final_grade_module(course_id)
        moodle_user_id = self.get_creds_of_user_in_course(course_id, user_id)

        params = {
            'wsfunction': 'core_grades_update_grades',
            'source': module_name,
            'courseid': course_id,
            'component': 'mod_assign',
            'activityid': course_module_id,
            'itemnumber': 0,
            'grades[0][studentid]': moodle_user_id,
            # The grade is exported as a decimal between [0-1]
            'grades[0][grade]': completion_data['grade'] * 100
        }
        return self._post(params)

    @moodle_request_wrapper
    def create_content_metadata(self, serialized_data):
        """
        The below assumes the data is dict/object.
        Format should look like:
        {
          courses[0][shortname]: 'value',
          courses[0][fullname]: 'value',
          [...]
          courses[1][shortname]: 'value',
          courses[1][fullname]: 'value',
          [...]
        }
        """
        serialized_data['wsfunction'] = 'core_course_create_courses'
        response = self._post(serialized_data)
        return response

    @moodle_request_wrapper
    def update_content_metadata(self, serialized_data):
        moodle_course_id = self.get_course_id(serialized_data['courses[0][shortname]'])
        serialized_data['courses[0][id]'] = moodle_course_id
        serialized_data['wsfunction'] = 'core_course_update_courses'
        return self._post(serialized_data)

    @moodle_request_wrapper
    def delete_content_metadata(self, serialized_data):
        moodle_course_id = self.get_course_id(serialized_data['courses[0][shortname]'])
        params = {
            'wsfunction': 'core_course_delete_courses',
            'courseids[]': moodle_course_id
        }
        return self._post(params)

    def create_course_completion(self, user_id, payload):
        """Send course completion data to Moodle"""
        # The base integrated channels transmitter expects a tuple of (code, body),
        # but we need to wrap the requests
        resp = self._wrapped_create_course_completion(user_id, payload)
        return resp.status_code, resp.text

    @moodle_request_wrapper
    def delete_course_completion(self, user_id, payload):  # pylint: disable=unused-argument
        pass
