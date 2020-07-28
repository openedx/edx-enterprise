# -*- coding: utf-8 -*-
"""
Tests for clients in integrated_channels.
"""

import datetime
import unittest
import pytest

from six.moves.urllib.parse import urljoin  # pylint: disable=import-error
from freezegun import freeze_time

from django.utils import timezone

from integrated_channels.canvas.client import CanvasAPIClient
from test_utils import canvas_factories

NOW = datetime.datetime(2017, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
NOW_TIMESTAMP_FORMATTED = NOW.strftime('%F')


@freeze_time(NOW)
@pytest.mark.django_db
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
            "expires_in": "",
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

    def test_global_canvas_config_is_set(self):
        """ Test  _get_oauth_access_token with non json type response"""
        canvas_api_client = CanvasAPIClient(self.enterprise_config)
        expected_config = {}
        assert canvas_api_client.global_canvas_config == expected_config
