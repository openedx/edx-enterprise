# -*- coding: utf-8 -*-
"""
Client for connecting to CSOD Web Services.
"""
from __future__ import absolute_import, unicode_literals

import datetime
import time

import requests
from integrated_channels.exceptions import ClientError
from integrated_channels.integrated_channel.client import IntegratedChannelApiClient

from django.apps import apps


class CSODWebServicesAPIClient(IntegratedChannelApiClient):  # pylint: disable=abstract-method
    """
    Client for connecting to Cornerstone.

    Specifically, this class supports obtaining access tokens and posting to the courses and
     completion status endpoints.
    """
    
    def __init__(self, enterprise_configuration):
        """
        Instantiate a new client.

        Args:
            enterprise_configuration (DegreedEnterpriseCustomerConfiguration): An enterprise customers's
            configuration model for connecting with Degreed
        """
        super(CSODWebServicesAPIClient, self).__init__(enterprise_configuration)
        self.global_cornerstone_config = apps.get_model('degreed', 'CSODWebServicesGlobalConfiguration').current()

    def create_course_completion(self, user_id, payload):
        """
        Send a completion status payload to the Cornerstone complete endpoint

        Args:
            user_id (str): The sap user id that the completion status is being sent for.
            payload (str): JSON encoded object (serialized from CornerstoneLearnerDataTransmissionAudit)
                containing completion status fields per Cornerstone documentation.

        Returns:
            The body of the response from Cornerstone, if successful
        Raises:
            HTTPError: if we received a failure response code from Cornerstone
        """
        pass

    def delete_course_content(self, payload):
        """
        Delete a course in the upstream Cornerstone Course Catalog.

        Args:
            payload: JSON encoded object containing the required course data for deletion.

        Returns:
            A tuple containing the status code and the body of the response.
        Raises:
            HTTPError: if we received a failure response code from Cornerstone.
        """
        pass

    def create_course_content(self, payload):
        """
        Send courses payload to the Cornerstone create LO endpoint

        Args:
            payload: JSON encoded object containing course import data per Cornerstone documentation.

        Returns:
            The body of the response from Cornerstone, if successful
        Raises:
            HTTPError: if we received a failure response code from Cornerstone
        """
        pass

    def create_content_metadata(self, serialized_data):
        """
        Create content metadata records using the Cornerstone create LO endpoint.

        Arguments:
            serialized_data: Serialized JSON string representing a list of content metadata items.

        Raises:
            ClientError: If Cornerstone API call fails.
        """
        pass

    def update_content_metadata(self, serialized_data):
        """
        Update content metadata records using the Cornerstone update LO endpoint.

        Arguments:
            serialized_data: Serialized JSON string representing a list of content metadata items.

        Raises:
            ClientError: If Cornerstone API call fails.
        """
        pass

    def delete_content_metadata(self, serialized_data):
        """
        Delete content metadata records using the Cornerstone delete LO endpoint.

        Arguments:
            serialized_data: Serialized JSON string representing a list of content metadata items.

        Raises:
            ClientError: If Cornerstone API call fails.
        """
        pass
