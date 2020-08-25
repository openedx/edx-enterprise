# -*- coding: utf-8 -*-
"""
Client for connecting to Moodle.
"""

import requests

from django.apps import apps

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

    def create_content_metadata(self, serialized_data):
        # The below assumes the data is dict/object.
        # Format should look like:
        # {
        #   courses[0][shortname]: 'value',
        #   courses[0][fullname]: 'value',
        #   [...]
        #   courses[1][shortname]: 'value',
        #   courses[1][fullname]: 'value',
        #   [...]
        # }

        serialized_data['wstoken'] = self.enterprise_configuration.api_token
        serialized_data['wsfunction'] = 'core_course_create_courses'
        #url = self.enterprise_configuration.moodle_base_url + '?{}'.format(urlencode(base_params)) + serialized_data
        response = requests.post(
            self.enterprise_configuration.moodle_base_url,
            params=serialized_data
        )
        return response.status_code, response.text


    def update_content_metadata(self, serialized_data):
        # core_course_get_courses_by_field (idnumber or shortname field as our unique match)
        # Get course id from above call first. Then hit update function based on that id.
        # May have to get and modify data in a loop here. Actual update call can be bulk though
        # core_course_update_courses
        pass

    def delete_content_metadata(self, serialized_data):
        # core_course_get_courses_by_field (idnumber or shortname field as our unique match)
        # Delete by core_course_delete_courses
        pass
