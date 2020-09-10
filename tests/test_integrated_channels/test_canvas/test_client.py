# -*- coding: utf-8 -*-
"""
Tests for clients in integrated_channels.
"""

import datetime
import json
import random
import unittest

import pytest
import responses
from freezegun import freeze_time
from six.moves.urllib.parse import urljoin  # pylint: disable=import-error

from django.utils import timezone

from integrated_channels.canvas.client import CanvasAPIClient
from integrated_channels.exceptions import ClientError
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
        self.account_id = random.randint(1, 1000)
        self.canvas_email = "test@test.com"
        self.canvas_user_id = random.randint(1, 1000)
        self.canvas_course_id = random.randint(1, 1000)
        self.canvas_assignment_id = random.randint(1, 1000)
        self.course_id = "edx+111"
        self.course_grade = random.random()
        self.url_base = "http://betatest.instructure.com"
        self.oauth_token_auth_path = "/login/oauth2/token"
        self.oauth_url = urljoin(self.url_base, self.oauth_token_auth_path)
        self.update_url = urljoin(self.url_base, "/api/v1/courses/")
        self.canvas_users_url = "{base}/api/v1/accounts/{account_id}/users?search_term={email_address}".format(
            base=self.url_base,
            account_id=self.account_id,
            email_address=self.canvas_email
        )
        self.canvas_user_courses_url = "{base}/api/v1/users/{canvas_user_id}/courses".format(
            base=self.url_base,
            canvas_user_id=self.canvas_user_id
        )
        self.canvas_course_assignments_url = "{base}/api/v1/courses/{course_id}/assignments".format(
            base=self.url_base,
            course_id=self.canvas_course_id
        )
        self.canvas_assignment_url = \
            "{base}/api/v1/courses/{course_id}/assignments/{assignment_id}/submissions/{user_id}".format(
                base=self.url_base,
                course_id=self.canvas_course_id,
                assignment_id=self.canvas_assignment_id,
                user_id=self.canvas_user_id
            )
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
        self.integration_id = 'course-v1:{course_id}+2T2020'.format(course_id=self.course_id)
        self.course_completion_date = datetime.date(
            2020,
            random.randint(1, 10),
            random.randint(1, 10)
        )
        self.course_completion_payload = \
            '{{"completedTimestamp": "{completion_date}", "courseCompleted": "true", '\
            '"courseID": "{course_id}", "grade": "{course_grade}", "userID": "{email}"}}'.format(
                completion_date=self.course_completion_date,
                course_id=self.course_id,
                email=self.canvas_email,
                course_grade=self.course_grade,
            )

    def update_fails_with_poorly_formatted_data(self, request_type):
        """
        Helper method to test error handling with poorly formatted data
        """
        poorly_formatted_data = 'this is a string, not a bytearray'
        canvas_api_client = CanvasAPIClient(self.enterprise_config)

        with pytest.raises(ClientError) as client_error:
            with responses.RequestsMock() as request_mock:
                request_mock.add(
                    responses.POST,
                    self.oauth_url,
                    json={'access_token': self.access_token},
                    status=200
                )
                transmitter_method = getattr(canvas_api_client, request_type)
                transmitter_method(poorly_formatted_data)

        assert client_error.value.__str__() == 'Unable to decode data.'

    def update_fails_with_poorly_constructed_data(self, request_type):
        """
        Helper method to test error handling with poorly constructed data
        """
        bad_course_to_update = '{"course": {"name": "test_course"}}'.encode()
        canvas_api_client = CanvasAPIClient(self.enterprise_config)

        with pytest.raises(ClientError) as client_error:
            with responses.RequestsMock() as request_mock:
                request_mock.add(
                    responses.POST,
                    self.oauth_url,
                    json={'access_token': self.access_token},
                    status=200
                )
                transmitter_method = getattr(canvas_api_client, request_type)
                transmitter_method(bad_course_to_update)

        assert client_error.value.__str__() == '' \
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

        with pytest.raises(ClientError) as client_error:
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

        assert client_error.value.__str__() == 'No Canvas courses found' \
                                               ' with associated integration ID: {}.'.format(self.integration_id)

    def transmission_with_empty_data(self, request_type):
        """
        Helper method to test error handling with empty data
        """
        empty_data = ''
        canvas_api_client = CanvasAPIClient(self.enterprise_config)

        with pytest.raises(ClientError) as client_error:
            with responses.RequestsMock() as request_mock:
                request_mock.add(
                    responses.POST,
                    self.oauth_url,
                    json={'access_token': self.access_token},
                    status=200
                )
                transmitter_method = getattr(canvas_api_client, request_type)
                transmitter_method(empty_data)

        assert client_error.value.__str__() == 'No data to transmit.'

    def test_course_completion_with_no_canvas_user(self):
        """Test that we properly raise exceptions if the client can't find the edx user in Canvas"""

        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET,
                self.canvas_users_url,
                body="[]",
                status=200
            )
            rsps.add(
                responses.POST,
                self.oauth_url,
                json={"access_token": self.access_token},
                status=200
            )
            canvas_api_client = CanvasAPIClient(self.enterprise_config)
            with pytest.raises(ClientError) as client_error:
                canvas_api_client.create_course_completion(self.canvas_email, self.course_completion_payload)

            assert client_error.value.__str__() == 'No Canvas user ID ' \
                                                   'found associated with email: {}'.format(self.canvas_email)

    def test_course_completion_with_no_matching_canvas_course(self):
        """Test that we properly raise exceptions for when a course is not found in canvas."""
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.POST,
                self.oauth_url,
                json={"access_token": self.access_token},
                status=200
            )
            rsps.add(
                responses.GET,
                self.canvas_users_url,
                json=[{'sortable_name': 'test user', 'login_id': self.canvas_email, 'id': self.canvas_user_id}],
                status=200
            )
            rsps.add(
                responses.GET,
                self.canvas_user_courses_url,
                json=[]
            )
            canvas_api_client = CanvasAPIClient(self.enterprise_config)
            with pytest.raises(ClientError) as client_error:
                canvas_api_client.create_course_completion(self.canvas_email, self.course_completion_payload)

            assert client_error.value.__str__() == \
                "Course: {course_id} not found registered in Canvas for Edx " \
                "learner: {canvas_email}/Canvas learner: {canvas_user_id}.".format(
                    course_id=self.course_id,
                    canvas_email=self.canvas_email,
                    canvas_user_id=self.canvas_user_id
                )  # noqa

    def test_course_completion_grade_submission_500s(self):
        """Test that we raise the error if Canvas experiences a 500 while posting course completion data"""
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.POST,
                self.oauth_url,
                json={"access_token": self.access_token},
                status=200
            )
            rsps.add(
                responses.GET,
                self.canvas_users_url,
                json=[{'sortable_name': 'test user', 'login_id': self.canvas_email, 'id': self.canvas_user_id}],
                status=200
            )
            rsps.add(
                responses.GET,
                self.canvas_user_courses_url,
                json=[{
                    'integration_id': self.integration_id,
                    'id': self.canvas_course_id
                }]
            )
            rsps.add(
                responses.GET,
                self.canvas_course_assignments_url,
                json=[{'integration_id': self.integration_id, 'id': self.canvas_assignment_id}]
            )
            rsps.add(
                responses.PUT,
                self.canvas_assignment_url,
                body=Exception('something went wrong')
            )
            canvas_api_client = CanvasAPIClient(self.enterprise_config)
            with pytest.raises(Exception) as client_error:
                canvas_api_client.create_course_completion(self.canvas_email, self.course_completion_payload)
            assert client_error.value.__str__() == 'something went wrong'

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

            expected_resp = '{"id": 1}'
            request_mock.add(
                responses.POST,
                CanvasAPIClient.course_create_endpoint(self.url_base, self.account_id),
                status=201,
                body=expected_resp
            )
            status_code, response_text = canvas_api_client.create_content_metadata(course_to_create)
            assert status_code == 201
            assert response_text == expected_resp

    def test_create_course_success_with_image_url(self):
        canvas_api_client = CanvasAPIClient(self.enterprise_config)
        course_to_create = json.dumps({
            "course": {
                "integration_id": self.integration_id,
                "name": "test_course_create",
                "image_url": "http://image.one/url.png"
            }
        }).encode('utf-8')

        with responses.RequestsMock() as request_mock:
            request_mock.add(
                responses.POST,
                self.oauth_url,
                json={'access_token': self.access_token},
                status=200
            )

            expected_resp = '{"id": 1111}'
            request_mock.add(
                responses.POST,
                CanvasAPIClient.course_create_endpoint(self.url_base, self.account_id),
                status=201,
                body=expected_resp
            )
            request_mock.add(
                responses.PUT,
                CanvasAPIClient.course_update_endpoint(self.url_base, 1111),
                status=200
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
