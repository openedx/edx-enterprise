"""
Tests for Degreed2 client for integrated_channels.
"""

import json
import unittest

import pytest
import responses

from django.apps import apps

from integrated_channels.cornerstone.client import CornerstoneAPIClient
from test_utils import factories

IntegratedChannelAPIRequestLogs = apps.get_model(
    "integrated_channel", "IntegratedChannelAPIRequestLogs"
)


@pytest.mark.django_db
class TestCornerstoneApiClient(unittest.TestCase):
    """
    Test Degreed2 API client methods.
    """

    def setUp(self):
        super().setUp()
        self.cornerstone_base_url = "https://edx.example.com/"
        self.csod_config = factories.CornerstoneEnterpriseCustomerConfigurationFactory(
            cornerstone_base_url=self.cornerstone_base_url
        )

    @responses.activate
    def test_create_course_completion_stores_api_record(self):
        """
        ``create_course_completion`` should use the appropriate URLs for transmission.
        """
        cornerstone_api_client = CornerstoneAPIClient(self.csod_config)
        callbackUrl = "dummy_callback_url"
        sessionToken = "dummy_session_oken"
        payload = {
            "data": {
                "userGuid": "dummy_id",
                "sessionToken": sessionToken,
                "callbackUrl": callbackUrl,
                "subdomain": "dummy_subdomain",
            }
        }
        responses.add(
            responses.POST,
            f"{self.cornerstone_base_url}{callbackUrl}?sessionToken={sessionToken}",
            json="{}",
            status=200,
        )
        assert IntegratedChannelAPIRequestLogs.objects.count() == 0
        output = cornerstone_api_client.create_course_completion(
            "test-learner@example.com", json.dumps(payload)
        )
        assert IntegratedChannelAPIRequestLogs.objects.count() == 1
        assert len(responses.calls) == 1
        assert output == (200, '"{}"')

    @unittest.mock.patch('integrated_channels.cornerstone.client.LOGGER')
    def test_cleanup_duplicate_assignment_records_logging(self, mock_logger):
        """
        Test that cleanup_duplicate_assignment_records logs the not implemented message correctly.
        """
        cornerstone_api_client = CornerstoneAPIClient(self.csod_config)

        # Call the method with dummy courses
        cornerstone_api_client.cleanup_duplicate_assignment_records(['course1', 'course2'])

        # Verify the logging call was made with correct parameters
        mock_logger.error.assert_called_once()
        args, kwargs = mock_logger.error.call_args
        self.assertEqual(args[0], "Cornerstone integrated channel does not yet support assignment deduplication.")
        self.assertEqual(kwargs['extra']['channel_name'], self.csod_config.channel_code())
        self.assertEqual(kwargs['extra']['enterprise_customer_uuid'], self.csod_config.enterprise_customer.uuid)
