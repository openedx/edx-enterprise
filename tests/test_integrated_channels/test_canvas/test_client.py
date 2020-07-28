# -*- coding: utf-8 -*-
"""
Tests for clients in integrated_channels.
"""

import datetime
import unittest
import pytest
from freezegun import freeze_time
from six.moves.urllib.parse import urljoin  # pylint: disable=import-error

from django.utils import timezone
import responses

from integrated_channels.canvas.client import CanvasAPIClient
from test_utils import canvas_factories

NOW = datetime.datetime(2017, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
NOW_TIMESTAMP_FORMATTED = NOW.strftime('%F')


@freeze_time(NOW)
@pytest.mark.django_db
@pytest.mark.skip('Can only run once key field is removed from db, since it was marked Not Null')
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
        self.account_id = 2000
        self.access_token = "access_token"
        self.expected_token_response_body = {
            "expires_in": "",
            "access_token": self.access_token
        }
        canvas_factories.CanvasGlobalConfigurationFactory(
            course_api_path=self.course_api_path
        )
        self.enterprise_config = canvas_factories.CanvasEnterpriseCustomerConfigurationFactory(
            client_id=self.client_id,
            client_secret=self.client_secret,
            canvas_account_id=self.account_id,
            canvas_base_url=self.url_base,
        )

    def test_global_canvas_config_is_set(self):
        """ Test  global_canvas_config is setup"""
        canvas_api_client = CanvasAPIClient(self.enterprise_config)
        assert canvas_api_client.global_canvas_config is not None
        assert canvas_api_client.global_canvas_config.id == 1
