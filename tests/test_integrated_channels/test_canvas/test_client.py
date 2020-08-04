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
from integrated_channels.exceptions import ClientError
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
        self.oauth_token_auth_path = "login/oauth2/token"
        self.oauth_url = urljoin(self.url_base, self.oauth_token_auth_path)
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
        self.refresh_token = "refresh_token"
        canvas_factories.CanvasGlobalConfigurationFactory(
            course_api_path=self.course_api_path
        )
        self.enterprise_config = canvas_factories.CanvasEnterpriseCustomerConfigurationFactory(
            client_id=self.client_id,
            client_secret=self.client_secret,
            canvas_account_id=self.account_id,
            canvas_base_url=self.url_base,
            refresh_token=self.refresh_token,
        )

    def test_create_client_session_with_oauth_access_key(self):
        """ Test instantiating the client will fetch and set the session's oauth access key"""
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.POST,
                self.oauth_url,
                json={"access_token": self.access_token},
                status=200
            )
            canvas_api_client = CanvasAPIClient(self.enterprise_config)
            canvas_api_client._create_session()  # pylint: disable=protected-access

            assert canvas_api_client.session.headers['Authorization'] == "Bearer " + self.access_token

    def test_client_instantiation_fails_without_client_id(self):
        with pytest.raises(ClientError) as client_error:
            self.enterprise_config.client_id = None
            canvas_api_client = CanvasAPIClient(self.enterprise_config)
            canvas_api_client._create_session()  # pylint: disable=protected-access
        assert client_error.value.__str__() == 'Failed to generate oauth access token: Client ID required.'

    def test_client_instantiation_fails_without_client_secret(self):
        with pytest.raises(ClientError) as client_error:
            self.enterprise_config.client_secret = None
            canvas_api_client = CanvasAPIClient(self.enterprise_config)
            canvas_api_client._create_session()  # pylint: disable=protected-access
        assert client_error.value.__str__() == 'Failed to generate oauth access token: Client secret required.'

    def test_client_instantiation_fails_without_refresh_token(self):
        with pytest.raises(ClientError) as client_error:
            self.enterprise_config.refresh_token = None
            canvas_api_client = CanvasAPIClient(self.enterprise_config)
            canvas_api_client._create_session()  # pylint: disable=protected-access
        assert client_error.value.__str__() == 'Failed to generate oauth access token: Refresh token required.'

    def test_global_canvas_config_is_set(self):
        """ Test  global_canvas_config is setup"""
        canvas_api_client = CanvasAPIClient(self.enterprise_config)
        assert canvas_api_client.global_canvas_config is not None
        assert canvas_api_client.global_canvas_config.id == 1
