"""
Tests for Degreed2 client for integrated_channels.
"""

import json
import unittest

import pytest
import responses
from freezegun import freeze_time

from django.apps.registry import apps

from integrated_channels.cornerstone.client import CornerstoneAPIClient
from test_utils import factories


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
    def test_create_course_completion(self):
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
        output = cornerstone_api_client.create_course_completion(
            "test-learner@example.com", json.dumps(payload)
        )

        assert len(responses.calls) == 1
        assert output == (200, '"{}"')
