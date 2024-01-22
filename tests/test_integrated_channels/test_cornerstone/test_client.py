"""
Tests for Degreed2 client for integrated_channels.
"""

import datetime
import json
import unittest

import mock
import pytest
import requests
import responses
from freezegun import freeze_time
from six.moves.urllib.parse import urljoin

from django.apps.registry import apps

from enterprise.api_client.enterprise_catalog import EnterpriseCatalogApiClient
from enterprise.models import EnterpriseCustomerUser
from integrated_channels.cornerstone.client import CornerstoneAPIClient
from integrated_channels.exceptions import ClientError
from test_utils import factories

NOW = datetime.datetime(2017, 1, 2, 3, 4, 5, tzinfo=datetime.timezone.utc)
NOW_TIMESTAMP_FORMATTED = NOW.strftime("%F")


def create_course_payload():
    return json.dumps(
        {
            "courses": [
                {
                    "title": "title",
                    "summary": "description",
                    "image-url": "image",
                    "url": "enrollment_url",
                    "language": "content_language",
                    "external-id": "key",
                    "duration": "duration",
                    "duration-type": "Days",
                }
            ],
        },
        sort_keys=True,
    ).encode("utf-8")


@pytest.mark.django_db
@freeze_time(NOW)
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

        assert output == (200, '"{}"')
        # assert len(responses.calls) == 2
        # assert responses.calls[0].request.url == cornerstone_api_client.get_oauth_url()
        # assert responses.calls[1].request.url == cornerstone_api_client.get_completions_url()
