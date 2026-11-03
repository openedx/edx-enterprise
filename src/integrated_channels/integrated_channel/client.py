"""
Base API client for integrated channels.
"""

from enum import Enum


class IntegratedChannelHealthStatus(Enum):
    """
    Health status list for Integrated Channels
    """
    HEALTHY = 'HEALTHY'
    INVALID_CONFIG = 'INVALID_CONFIG'
    CONNECTION_FAILURE = 'CONNECTION_FAILURE'


class IntegratedChannelApiClient:
    """
    This is the interface to be implemented by API clients for integrated channels.
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

    def create_content_metadata(self, serialized_data):
        """
        Create content metadata using the integrated channel's API.
        """
        raise NotImplementedError()

    def update_content_metadata(self, serialized_data):
        """
        Update content metadata using the integrated channel's API.
        """
        raise NotImplementedError()

    def delete_content_metadata(self, serialized_data):
        """
        Delete content metadata using the integrated channel's API.
        """
        raise NotImplementedError()

    def create_assessment_reporting(self, user_id, payload):
        """
        Send a request to the integrated channel's grade API to update the assessment level reporting status for a user.
        """
        raise NotImplementedError()

    def cleanup_duplicate_assignment_records(self, courses):
        """
        Delete duplicate assignments transmitted through the integrated channel's API.
        """
        raise NotImplementedError()

    def health_check(self):
        """Check integrated channel's config health

        Returns: IntegratedChannelHealthStatus
            HEALTHY if configuration is valid
            INVALID_CONFIG if configuration is incomplete/invalid
        """
        is_valid = self.enterprise_configuration.is_valid
        missing_fields = is_valid[0]
        missing_ct = len(missing_fields['missing']) if 'missing' in missing_fields else 0
        incorrect_fields = is_valid[1]
        incorrect_ct = len(incorrect_fields['incorrect']) if 'incorrect' in incorrect_fields else 0
        if missing_ct > 0 or incorrect_ct > 0:
            return IntegratedChannelHealthStatus.INVALID_CONFIG
        else:
            return IntegratedChannelHealthStatus.HEALTHY
