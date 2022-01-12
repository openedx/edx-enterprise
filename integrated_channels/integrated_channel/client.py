"""
Base API client for integrated channels.
"""


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
