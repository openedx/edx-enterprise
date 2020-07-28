# -*- coding: utf-8 -*-
"""
Tests for clients in integrated_channels.
"""

import datetime
import json
import unittest

import pytest
import requests
import responses
from freezegun import freeze_time
from six.moves.urllib.parse import urljoin  # pylint: disable=import-error

from django.utils import timezone

from integrated_channels.canvas.client import CanvasAPIClient
from integrated_channels.exceptions import ClientError
from test_utils import canvas_factories

NOW = datetime.datetime(2017, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
NOW_TIMESTAMP_FORMATTED = NOW.strftime('%F')


@pytest.mark.django_db
@freeze_time(NOW)
class TestCanvasApiClient(unittest.TestCase):
    """
    Test Canvas API client methods.
    """

    def setUp(self):
        super(TestCanvasApiClient, self).setUp()
        self.url_base = "http://betatest.instructure.com/"
        self.oauth_api_path = "login/oauth2/token"
        self.oauth_url = urljoin(self.url_base, self.oauth_api_path)
        self.course_api_path = "api/v1/provider/content/course"
        self.course_url = urljoin(self.url_base, self.course_api_path)
        self.client_id = "client_id"
        self.client_secret = "client_secret"
        self.company_id = "company_id"
        self.access_token = "access_token"
        self.expected_token_response_body = {
            "expires_in": self.expires_in,
            "access_token": self.access_token
        }
        canvas_factories.CanvasGlobalConfigurationFactory(
            course_api_path=self.course_api_path,
            oauth_api_path=self.oauth_api_path,
        )
        self.enterprise_config = canvas_factories.CanvasEnterpriseCustomerConfigurationFactory(
            key=self.client_id,
            secret=self.client_secret,
            canvas_company_id=self.company_id,
            canvas_base_url=self.url_base,
        )

    @responses.activate
    def test_oauth_with_non_json_response(self):
        """ Test  _get_oauth_access_token with non json type response"""
        with pytest.raises(requests.RequestException):
            responses.add(
                responses.POST,
                self.oauth_url,
            )
            client = CanvasAPIClient(self.enterprise_config)
            client._get_oauth_access_token(  # pylint: disable=protected-access
                self.client_id,
                self.client_secret,
            )
