# -*- coding: utf-8 -*-
"""
Base API client for integrated channels.
"""

from __future__ import absolute_import, unicode_literals


class IntegratedChannelApiClient(object):
    """
    This is the interface to be implemented by API clients for integrated channels.

    The interface contains the following method(s):

    create_course_completion(user_id, payload)
        Makes a POST request to the integrated channel's completion API for the given user with information
        available in the payload.

    create_course_content(payload):
        Make a POST request to the integrated channel's course content API with course metadata available
        in the payload.
    """

    def __init__(self, enterprise_configuration):
        """
        Instantiate a new base client.

        Args:
            enterprise_configuration: An enterprise customers's configuration model for connecting with the channel

        Raises:
            ValueError: If an enterprise configuration is not provided.
        """
        if not enterprise_configuration:
            raise ValueError(
                'An Enterprise Customer Configuration is required to instantiate an Integrated Channel API client.'
            )
        self.enterprise_configuration = enterprise_configuration

    def create_course_completion(self, user_id, payload):
        """
        Make a POST request to the integrated channel's completion API to update completion status for a user.

        :param user_id: The ID of the user for whom completion status must be updated.
        :param payload: The JSON encoded payload containing the completion data.
        """
        raise NotImplementedError('Implement in concrete subclass.')

    def delete_course_completion(self, user_id, payload):
        """
        Make a DELETE request to the integrated channel's completion API to update completion status for a user.

        :param user_id: The ID of the user for whom completion status must be updated.
        :param payload: The JSON encoded payload containing the completion data.
        """
        raise NotImplementedError('Implement in concrete subclass.')

    def create_course_content(self, payload):
        """
        Make a POST request to the integrated channel's course content API to update course metadata.

        :param payload: The JSON encoded payload containing the course metadata.
        """
        raise NotImplementedError('Implement in concrete subclass.')

    def delete_course_content(self, payload):
        """
        Make a DELETE request to the integrated channel's course content API to update course metadata.

        :param payload: The JSON encoded payload containing the course metadata.
        """
        raise NotImplementedError('Implement in concrete subclass.')
