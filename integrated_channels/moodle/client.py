# -*- coding: utf-8 -*-
"""
Client for connecting to Moodle.
"""

from django.apps import apps
# from django.utils.http import urlencode

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
        # TODO: Intercept and fix serialized_data so it is an object not a binary string.
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

        # base_params = {
        #   'wstoken': self.enterprise_config.api_token,
        #   'wsfunction': 'core_course_create_courses',
        #   ???? I forgot the moodle json formatting field name and can't find it. :(
        # }
        # url = self.config.moodle_base_url + '?{}'.format(urlencode(base_params)) + '?{}'.format(urlencode(serialized_data))
        pass

    def update_content_metadata(self, serialized_data):
        pass

    def delete_content_metadata(self, serialized_data):
        pass
