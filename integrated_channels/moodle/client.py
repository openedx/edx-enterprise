# -*- coding: utf-8 -*-
"""
Client for connecting to Moodle.
"""

import json
import logging
from http import HTTPStatus
from urllib.parse import urljoin

import requests

from django.apps import apps

from integrated_channels.exceptions import ClientError
from integrated_channels.integrated_channel.client import IntegratedChannelApiClient
from integrated_channels.utils import generate_formatted_log

LOGGER = logging.getLogger(__name__)

MOODLE_FINAL_GRADE_ASSIGNMENT_NAME = '(edX integration) Final Grade'


class MoodleClientError(ClientError):
    """
    Indicate a problem when interacting with Moodle.
    """
    def __init__(self, message, status_code=500, moodle_error=None):
        """Save the status code and message raised from the client."""
        self.status_code = status_code
        self.message = message
        self.moodle_error = moodle_error
        super().__init__(message, status_code)


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
        except (AttributeError, ValueError) as error:
            # Moodle spits back an entire HTML page if something is wrong in our URL format.
            # This cannot be converted to JSON thus the above fails miserably.
            # The above can fail with different errors depending on the format of the returned page.
            # Moodle of course does not tell us what is wrong in any part of this HTML.
            log_msg = (f'Moodle API task "{method.__name__}" '
                       f'for enterprise_customer_uuid "{self.enterprise_configuration.enterprise_customer.uuid}" '
                       f'failed due to unknown error with code "{response.status_code}".')
            raise ClientError(log_msg, response.status_code) from error
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
            raise MoodleClientError(
                'Moodle API Client Task "{method}" failed with error code '
                '"{code}" and message: "{msg}" '.format(
                    method=method.__name__, code=error_code, msg=body.get('message'),
                ),
                response.status_code,
                error_code,
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
        super().__init__(enterprise_configuration)
        self.config = apps.get_app_config('moodle')
        self.token = enterprise_configuration.token or self._get_access_token()

    def _post(self, additional_params):
        """
        Compile common params and run request's post function
        """
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
        }
        params = {
            'wstoken': self.token,
            'moodlewsrestformat': 'json',
        }
        params.update(additional_params)

        response = requests.post(
            url='{url}{api_path}'.format(
                url=self.enterprise_configuration.moodle_base_url,
                api_path=self.MOODLE_API_PATH
            ),
            data=params,
            headers=headers
        )

        return response

    @moodle_request_wrapper
    def _wrapped_post(self, additional_params):
        """
        A version of _post which handles error cases, useful
        for when the caller wants to examine errors
        """
        return self._post(additional_params)

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
        except (KeyError, ValueError) as error:
            raise ClientError(
                "Failed to post access token. Received message={} from Moodle".format(response.text),
                response.status_code
            ) from error

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
            'field': 'idnumber',
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
        when sending 1 course and its a dupe, treat as success.
        when sending N courses and a dupe exists, throw exception since
        there is no easy way to retry with just the non-dupes.
        """
        # check to see if more than 1 course is being passed
        more_than_one_course = serialized_data.get('courses[1][shortname]')
        serialized_data['wsfunction'] = 'core_course_create_courses'
        try:
            self._wrapped_post(serialized_data)
        except MoodleClientError as error:
            # treat duplicate as successful, but only if its a single course
            # set chunk size settings to 1 if youre seeing a lot of these errors
            if error.moodle_error == 'shortnametaken' and not more_than_one_course:
                return True
            else:
                raise error
        return True

    @moodle_request_wrapper
    def update_content_metadata(self, serialized_data):
        moodle_course_id = self.get_course_id(serialized_data['courses[0][idnumber]'])
        serialized_data['courses[0][id]'] = moodle_course_id
        serialized_data['wsfunction'] = 'core_course_update_courses'
        return self._post(serialized_data)

    @moodle_request_wrapper
    def delete_content_metadata(self, serialized_data):
        response = self._get_courses(serialized_data['courses[0][idnumber]'])
        parsed_response = json.loads(response.text)
        if not parsed_response.get('courses'):
            LOGGER.info(
                generate_formatted_log(
                    self.enterprise_configuration.channel_code(),
                    self.enterprise_configuration.enterprise_customer.uuid,
                    None,
                    None,
                    'No course found while attempting to delete edX course: '
                    f'{serialized_data["courses[0][idnumber]"]} from moodle.'
                )
            )
            # Hacky way of getting around the request wrapper validation
            rsp = requests.Response()
            rsp._content = bytearray('{"result": "Course not found."}', 'utf-8')  # pylint: disable=protected-access
            return rsp
        moodle_course_id = parsed_response['courses'][0]['id']
        params = {
            'wsfunction': 'core_course_delete_courses',
            'courseids[]': moodle_course_id
        }
        return self._post(params)

    def create_assessment_reporting(self, user_id, payload):
        """
        Not implemented yet
        """

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
                "Moodle integrated channel does not yet support assignment deduplication."
            )
        )

    def create_course_completion(self, user_id, payload):
        """Send course completion data to Moodle"""
        # The base integrated channels transmitter expects a tuple of (code, body),
        # but we need to wrap the requests
        resp = self._wrapped_create_course_completion(user_id, payload)
        return resp.status_code, resp.text

    @moodle_request_wrapper
    def delete_course_completion(self, user_id, payload):
        pass
