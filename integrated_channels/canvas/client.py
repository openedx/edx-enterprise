# -*- coding: utf-8 -*-
"""
Client for connecting to Canvas.
"""

from django.apps import apps

from integrated_channels.integrated_channel.client import IntegratedChannelApiClient


class CanvasAPIClient(IntegratedChannelApiClient):
    """
    Client for connecting to Canvas.

    Code to obtain access tokens and posting to the courses and
    completion status endpoints.
    """

    def __init__(self, enterprise_configuration):
        """
        Instantiate a new client.

        Args:
            enterprise_configuration (CanvasEnterpriseCustomerConfiguration): An enterprise customers's
            configuration model for connecting with Canvas
        """
        super(CanvasAPIClient, self).__init__(enterprise_configuration)
        self.global_canvas_config = apps.get_model('canvas', 'CanvasGlobalConfiguration').current()
        self.session = None
        self.expires_at = None

    def create_course_completion(self, user_id, payload):  # pylint: disable=unused-argument
        pass

    def delete_course_completion(self, user_id, payload):  # pylint: disable=unused-argument
        pass

    def create_content_metadata(self, serialized_data):
        pass

    def update_content_metadata(self, serialized_data):
        pass

    def delete_content_metadata(self, serialized_data):
        pass

    def _get_oauth_access_token(self, client_id, client_secret):
        """
        TODO: get oauth token for canvas api access
        """
