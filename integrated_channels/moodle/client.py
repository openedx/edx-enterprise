# -*- coding: utf-8 -*-
"""
Client for connecting to Moodle.
"""

import json
from urllib.parse import urlencode, urljoin

import requests

from django.apps import apps

from integrated_channels.exceptions import ClientError
from integrated_channels.integrated_channel.client import IntegratedChannelApiClient


def moodle_request_wrapper(method):
    """
    Wraps requests to Moodle's API in a token check.
    Will obtain a new token if there isn't one.
    """
    def inner(self, *args, **kwargs):
        if not self.token:
            self.token = self._get_access_token()  # pylint: disable=protected-access
        response = method(self, *args, **kwargs)

        body = response.json()
        if isinstance(body, list):
            # On course creation (and ONLY course creation) success,
            # Moodle returns a list of JSON objects, because of course it does.
            # Otherwise, it fails instantly and returns actual JSON.
            return response
        error_code = body.get('errorcode')
        if error_code and error_code == 'invalidtoken':
            self.token = self._get_access_token()  # pylint: disable=protected-access
            response = method(self, *args, **kwargs)
        elif error_code:
            raise ClientError(
                'Moodle API Client Task "{method}" failed with error code '
                '"{code}" and message: "{msg}" '.format(
                    method=method.__name__, code=error_code, msg=body.get('message')
                )
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

    @moodle_request_wrapper
    def create_course_completion(self, user_id, payload):  # pylint: disable=unused-argument
        pass

    @moodle_request_wrapper
    def delete_course_completion(self, user_id, payload):  # pylint: disable=unused-argument
        pass

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
            raise ClientError('MoodleAPIClient request failed: 404 Course key '
                              '"{}" not found in Moodle.'.format(key))

        return parsed_response['courses'][0]['id']

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
        response = self._post(
            self.enterprise_configuration.moodle_base_url,
            serialized_data
        )
        return response

    @moodle_request_wrapper
    def update_content_metadata(self, serialized_data):
        for key in list(serialized_data):
            if 'shortname' in key:
                moodle_course_id = self.get_course_id(serialized_data[key])
                serialized_data[key.replace('shortname', 'id')] = moodle_course_id
        serialized_data['wsfunction'] = 'core_course_update_courses'
        return self._post(self.enterprise_configuration.moodle_base_url, serialized_data)

    @moodle_request_wrapper
    def delete_content_metadata(self, serialized_data):
        course_ids_to_delete = []
        for key in list(serialized_data):
            if 'shortname' in key:
                moodle_course_id = self.get_course_id(serialized_data[key])
                course_ids_to_delete.append(('courseids[]', moodle_course_id))
        params = {
            'wsfunction': 'core_course_delete_courses',
        }
        url = self.enterprise_configuration.moodle_base_url + \
            '?{}'.format(urlencode(course_ids_to_delete))
        return self._post(url, params)

    def _post(self, url, additional_params):
        """
        Compile common params and run request's post function
        """
        params = {
            'wstoken': self.token,
            'moodlewsrestformat': 'json',
        }
        params.update(additional_params)
        response = requests.post(
            url='{url}{api_path}?{querystring}'.format(
                url=url, api_path=self.MOODLE_API_PATH, querystring=urlencode(params)
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

        response.raise_for_status()
        try:
            data = response.json()
            token = data['token']
            return token
        except (KeyError, ValueError):
            raise requests.RequestException(response=response)
