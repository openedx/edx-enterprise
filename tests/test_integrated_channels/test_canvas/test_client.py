# -*- coding: utf-8 -*-
"""
Tests for clients in integrated_channels.
"""

import datetime
import json
import unittest

import pytest
import responses
from freezegun import freeze_time
from six.moves.urllib.parse import urljoin  # pylint: disable=import-error

from django.utils import timezone

from integrated_channels.canvas.client import CanvasAPIClient
from integrated_channels.exceptions import CanvasClientError, ClientError
from test_utils import factories

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
        self.account_id = 2000
        self.url_base = "http://betatest.instructure.com"
        self.oauth_token_auth_path = "/login/oauth2/token"
        self.oauth_url = urljoin(self.url_base, self.oauth_token_auth_path)
        self.update_url = urljoin(self.url_base, "/api/v1/courses/")
        self.get_all_courses_url = urljoin(self.url_base, "/api/v1/accounts/{}/courses/".format(self.account_id))
        self.course_api_path = "/api/v1/provider/content/course"
        self.course_url = urljoin(self.url_base, self.course_api_path)
        self.client_id = "client_id"
        self.client_secret = "client_secret"
        self.access_token = "access_token"
        self.expected_token_response_body = {
            "expires_in": "",
            "access_token": self.access_token
        }
        self.refresh_token = "refresh_token"
        self.enterprise_config = factories.CanvasEnterpriseCustomerConfigurationFactory(
            client_id=self.client_id,
            client_secret=self.client_secret,
            canvas_account_id=self.account_id,
            canvas_base_url=self.url_base,
            refresh_token=self.refresh_token,
        )
        self.integration_id = 'course-v1:test+TEST101'


    def update_fails_with_poorly_formatted_data(self, request_type):
        """
        Helper method to test error handling with poorly formatted data
        """
        poorly_formatted_data = 'this is a string, not a bytearray'
        canvas_api_client = CanvasAPIClient(self.enterprise_config)

        with pytest.raises(CanvasClientError) as client_error:
            with responses.RequestsMock() as request_mock:
                request_mock.add(
                    responses.POST,
                    self.oauth_url,
                    json={'access_token': self.access_token},
                    status=200
                )
                transmitter_method = getattr(canvas_api_client, request_type)
                transmitter_method(poorly_formatted_data)

        assert client_error.value.__str__() == 'Canvas Client Error: Unable to decode data.'

    def update_fails_with_poorly_constructed_data(self, request_type):
        """
        Helper method to test error handling with poorly constructed data
        """
        bad_course_to_update = '{"course": {"name": "test_course"}}'.encode()
        canvas_api_client = CanvasAPIClient(self.enterprise_config)

        with pytest.raises(CanvasClientError) as client_error:
            with responses.RequestsMock() as request_mock:
                request_mock.add(
                    responses.POST,
                    self.oauth_url,
                    json={'access_token': self.access_token},
                    status=200
                )
                transmitter_method = getattr(canvas_api_client, request_type)
                transmitter_method(bad_course_to_update)

        assert client_error.value.__str__() == 'Canvas Client Error: ' \
                                               'Could not transmit data, no integration ID present.'

    def update_fails_when_course_id_not_found(self, request_type):
        """
        Helper method to test error handling when no course ID is found
        """
        course_to_update = '{{"course": {{"integration_id": "{}", "name": "test_course"}}}}'.format(
            self.integration_id
        ).encode()
        mock_all_courses_resp = [
            {'name': 'wrong course', 'integration_id': 'wrong integration id', 'id': 2}
        ]
        canvas_api_client = CanvasAPIClient(self.enterprise_config)

        with pytest.raises(CanvasClientError) as client_error:
            with responses.RequestsMock() as request_mock:
                request_mock.add(
                    responses.GET,
                    self.get_all_courses_url,
                    json=mock_all_courses_resp,
                    status=200
                )
                request_mock.add(
                    responses.POST,
                    self.oauth_url,
                    json={'access_token': self.access_token},
                    status=200
                )
                transmitter_method = getattr(canvas_api_client, request_type)
                transmitter_method(course_to_update)

        assert client_error.value.__str__() == 'Canvas Client Error: No Canvas courses found' \
                                               ' with associated integration ID: {}.'.format(self.integration_id)

    def transmission_with_empty_data(self, request_type):
        """
        Helper method to test error handling with empty data
        """
        empty_data = ''
        canvas_api_client = CanvasAPIClient(self.enterprise_config)

        with pytest.raises(CanvasClientError) as client_error:
            with responses.RequestsMock() as request_mock:
                request_mock.add(
                    responses.POST,
                    self.oauth_url,
                    json={'access_token': self.access_token},
                    status=200
                )
                transmitter_method = getattr(canvas_api_client, request_type)
                transmitter_method(empty_data)

        assert client_error.value.__str__() == 'Canvas Client Error: No data to transmit.'

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

            assert canvas_api_client.session.headers["Authorization"] == "Bearer " + self.access_token

    def test_client_instantiation_fails_without_client_id(self):
        with pytest.raises(ClientError) as client_error:
            self.enterprise_config.client_id = None
            canvas_api_client = CanvasAPIClient(self.enterprise_config)
            canvas_api_client._create_session()  # pylint: disable=protected-access
        assert client_error.value.__str__() == "Failed to generate oauth access token: Client ID required."

    def test_client_instantiation_fails_without_client_secret(self):
        with pytest.raises(ClientError) as client_error:
            self.enterprise_config.client_secret = None
            canvas_api_client = CanvasAPIClient(self.enterprise_config)
            canvas_api_client._create_session()  # pylint: disable=protected-access
        assert client_error.value.__str__() == "Failed to generate oauth access token: Client secret required."

    def test_client_instantiation_fails_without_refresh_token(self):
        with pytest.raises(ClientError) as client_error:
            self.enterprise_config.refresh_token = None
            canvas_api_client = CanvasAPIClient(self.enterprise_config)
            canvas_api_client._create_session()  # pylint: disable=protected-access
        assert client_error.value.__str__() == "Failed to generate oauth access token: Refresh token required."

    def test_create_course_success(self):
        canvas_api_client = CanvasAPIClient(self.enterprise_config)
        course_to_create = json.dumps({
            "course": {
                "integration_id": self.integration_id,
                "name": "test_course_create"
            }
        }).encode()

        with responses.RequestsMock() as request_mock:
            request_mock.add(
                responses.POST,
                self.oauth_url,
                json={'access_token': self.access_token},
                status=200
            )

            expected_resp = '{id: 1}'
            request_mock.add(
                responses.POST,
                CanvasAPIClient.course_create_endpoint(self.url_base, self.account_id),
                status=201,
                body=expected_resp
            )
            status_code, response_text = canvas_api_client.create_content_metadata(course_to_create)
            assert status_code == 201
            assert response_text == expected_resp


    def test_course_delete_fails_with_empty_data(self):
        self.transmission_with_empty_data("delete_content_metadata")

    def test_course_update_fails_with_empty_data(self):
        self.transmission_with_empty_data("update_content_metadata")

    def test_course_delete_fails_with_poorly_formatted_data(self):
        self.update_fails_with_poorly_formatted_data("delete_content_metadata")

    def test_course_update_fails_with_poorly_formatted_data(self):
        self.update_fails_with_poorly_formatted_data("update_content_metadata")

    def test_course_delete_fails_with_poorly_constructed_data(self):
        self.update_fails_with_poorly_constructed_data("delete_content_metadata")

    def test_course_update_fails_with_poorly_constructed_data(self):
        self.update_fails_with_poorly_constructed_data("update_content_metadata")

    def test_course_delete_fails_when_course_id_not_found(self):
        self.update_fails_when_course_id_not_found("delete_content_metadata")

    def test_course_update_fails_when_course_id_not_found(self):
        self.update_fails_when_course_id_not_found("update_content_metadata")

    def test_successful_client_update(self):
        """
        Test the full workflow of a Canvas integrated channel client update request
        """
        course_to_update = json.dumps({
            "course": {"integration_id": self.integration_id, "name": "test_course"}
        }).encode()
        course_id = 1
        mock_all_courses_resp = [
            {'name': 'test course', 'integration_id': self.integration_id, 'id': course_id},
            {'name': 'wrong course', 'integration_id': 'wrong integration id', 'id': 2}
        ]
        canvas_api_client = CanvasAPIClient(self.enterprise_config)

        with responses.RequestsMock() as request_mock:
            request_mock.add(
                responses.GET,
                self.get_all_courses_url,
                json=mock_all_courses_resp,
                status=200
            )
            request_mock.add(
                responses.POST,
                self.oauth_url,
                json={'access_token': self.access_token},
                status=200
            )
            request_mock.add(
                responses.PUT,
                self.update_url + str(course_id),
                body=b'Mock update response text'
            )
            canvas_api_client.update_content_metadata(course_to_update)
