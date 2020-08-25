# -*- coding: utf-8 -*-
"""
Client for connecting to Moodle.
"""

import json
import requests

from django.apps import apps
from django.utils.http import urlencode
from urllib.parse import urlencode

from integrated_channels.integrated_channel.client import IntegratedChannelApiClient


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
    """

    def __init__(self, enterprise_configuration):
        """
        Instantiate a new client.

        Args:
            enterprise_configuration (MoodleEnterpriseCustomerConfiguration): An enterprise customers's
            configuration model for connecting with Moodle
        """
        super(MoodleAPIClient, self).__init__(enterprise_configuration)
        self.config = apps.get_app_config('moodle')

    def create_course_completion(self, user_id, payload):  # pylint: disable=unused-argument
        pass

    def delete_course_completion(self, user_id, payload):  # pylint: disable=unused-argument
        pass

    def _get_course_id(self, key):
        """
        Gets the Moodle course id (because we cannot update/delete without it).
        """
        params = {
            'wstoken': self.enterprise_configuration.api_token,
            'wsfunction': 'core_course_get_courses_by_field',
            'field': 'shortname',
            'value': key,
            'moodlewsrestformat': 'json'
        }
        response = requests.get(
            self.enterprise_configuration.moodle_base_url,
            params=params
        )

        return json.loads(response.text)['courses'][0]['id']

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

        serialized_data['wstoken'] = self.enterprise_configuration.api_token
        serialized_data['wsfunction'] = 'core_course_create_courses'
        #url = self.enterprise_configuration.moodle_base_url + '?{}'.format(urlencode(base_params)) + serialized_data
        response = requests.post(
            self.enterprise_configuration.moodle_base_url,
            params=serialized_data
        )
        return response.status_code, response.text


    def update_content_metadata(self, serialized_data):
        for key in list(serialized_data):
            if 'shortname' in key:
                moodle_course_id = self._get_course_id(serialized_data[key])
                serialized_data[key.replace('shortname', 'id')] = moodle_course_id
        serialized_data['wstoken'] = self.enterprise_configuration.api_token
        serialized_data['wsfunction'] = 'core_course_update_courses'
        response = requests.post(
            self.enterprise_configuration.moodle_base_url,
            params=serialized_data
        )
        return response.status_code, response.text

    def delete_content_metadata(self, serialized_data):
        course_ids_to_delete = []
        for key in list(serialized_data):
            if 'shortname' in key:
                moodle_course_id = self._get_course_id(serialized_data[key])
                course_ids_to_delete.append(('courseids[]', moodle_course_id))
        params = {
            'wstoken': self.enterprise_configuration.api_token,
            'wsfunction': 'core_course_delete_courses',
            'moodlewsrestformat': 'json',
        }
        url = self.enterprise_configuration.moodle_base_url + \
            '?{}'.format(urlencode(course_ids_to_delete))
        response = requests.post(
            url,
            params=params
        )
        return response.status_code, response.text
