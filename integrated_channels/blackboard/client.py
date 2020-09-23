# -*- coding: utf-8 -*-
"""
Client for connecting to Blackboard.
"""
from django.apps import apps

from integrated_channels.integrated_channel.client import IntegratedChannelApiClient


class BlackboardAPIClient(IntegratedChannelApiClient):
    """
    Client for connecting to Blackboard.
    TODO: Full implementation.
    """

    def __init__(self, enterprise_configuration):
        """
        Instantiate a new client.

        Args:
            enterprise_configuration (BlackboardEnterpriseCustomerConfiguration): An enterprise customers's
            configuration model for connecting with Blackboard
        """
        super(BlackboardAPIClient, self).__init__(enterprise_configuration)
        self.config = apps.get_app_config('blackboard')

    def create_content_metadata(self, serialized_data):
        """TODO"""

    def update_content_metadata(self, serialized_data):
        """TODO"""

    def delete_content_metadata(self, serialized_data):
        """TODO"""

    def create_course_completion(self, user_id, payload):  # pylint: disable=unused-argument
        """TODO"""

    def delete_course_completion(self, user_id, payload):  # pylint: disable=unused-argument
        """TODO"""
