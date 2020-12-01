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
            "{base}/api/v1/courses/{course_id}/assignments".format(
                base=self.url_base,
                course_id=self.canvas_course_id,
            )
        self.canvas_submission_url = \
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

    def _token_response(self):
        """Creates a token response with the stored access token, for testing"""
        return {'access_token': self.access_token, 'expires_in': 10}

    def test_expires_at_is_updated_after_session_expiry(self):
        canvas_api_client = CanvasAPIClient(self.enterprise_config)

        with responses.RequestsMock() as rsps:
            orig_time = datetime.datetime.utcnow()
            rsps.add(
                responses.POST,
                self.oauth_url,
                json={'access_token': self.access_token, 'expires_in': 1},
                status=200
            )
            canvas_api_client._create_session()  # pylint: disable=protected-access
            assert canvas_api_client.expires_at is not None
            orig_expires_at = canvas_api_client.expires_at

            # let's call again sometime later ensuring expiry
            with freeze_time(orig_time + datetime.timedelta(seconds=1.1)):
                canvas_api_client._create_session()  # pylint: disable=protected-access
                assert canvas_api_client.expires_at > orig_expires_at

    def test_search_for_canvas_user_with_400(self):
        """
        Test that we properly raise exceptions if the client can't find the edx user in Canvas while reporting
        grades (assessment and course level reporting both use the same method of retrieval).
        """
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET,
                self.canvas_users_url,
                body="[]",
                status=200
            )
            canvas_api_client = CanvasAPIClient(self.enterprise_config)

            # Searching for canvas users will require the session to be created
            rsps.add(
                responses.POST,
                self.oauth_url,
                json=self._token_response(),
                status=200
            )
            canvas_api_client._create_session()  # pylint: disable=protected-access

            with pytest.raises(ClientError) as client_error:
                canvas_api_client._search_for_canvas_user_by_email(self.canvas_email)  # pylint: disable=protected-access
                assert client_error.value.message == \
                    "Course: {course_id} not found registered in Canvas for Edx " \
                    "learner: {canvas_email}/Canvas learner: {canvas_user_id}.".format(
                        course_id=self.course_id,
                        canvas_email=self.canvas_email,
                        canvas_user_id=self.canvas_user_id
                    )

    def test_assessment_reporting_with_no_canvas_course_found(self):
        """
        Test that reporting assessment level data raises the proper exception when no Canvas course is found.

        **NOTE**
        This process is nearly identical to course level reporting except for the fact that course level reporting
        accounts for retrieved Canvas integration ID's that match both course IDs and course run IDs. As such, a common
        handler function is not ideal and the integration ID to course run ID matching is done on the
        create_assessment_reporting level.
        """
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.POST,
                self.oauth_url,
                json=self._token_response(),
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
                canvas_api_client.create_assessment_reporting(self.canvas_email, self.course_completion_payload)
                assert client_error.value.message == \
                    "Course: {course_id} not found registered in Canvas for Edx " \
                    "learner: {canvas_email}/Canvas learner: {canvas_user_id}.".format(
                        course_id=self.course_id,
                        canvas_email=self.canvas_email,
                        canvas_user_id=self.canvas_user_id
                    )

    def test_course_completion_with_no_matching_canvas_course(self):
        """
        Test that reporting course completion data raises the proper exception when no Canvas course is found.

        **NOTE**
        This process is nearly identical to assessment level grade reporting except for the fact that course level
        reporting accounts for retrieved Canvas integration ID's that match both course IDs and course run IDs. As such,
        a common handler function is not ideal and the integration ID to course/course run ID matching is done on the
        create_course_completion level.
        """
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.POST,
                self.oauth_url,
                json=self._token_response(),
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
                assert client_error.value.message == \
                    "Course: {course_id} not found registered in Canvas for Edx " \
                    "learner: {canvas_email}/Canvas learner: {canvas_user_id}.".format(
                        course_id=self.course_id,
                        canvas_email=self.canvas_email,
                        canvas_user_id=self.canvas_user_id
                    )

    def test_grade_reporting_get_assignment_500s(self):
        """
        Test that the client raises the appropriate error if Canvas responds with an error after the client requests
        course assignments.
        """
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET,
                self.canvas_assignment_url,
                json={'error': 'something went wrong'},
                status=400
            )
            canvas_api_client = CanvasAPIClient(self.enterprise_config)

            # Creating a Canvas assignment will require the session to be created
            rsps.add(
                responses.POST,
                self.oauth_url,
                json=self._token_response(),
                status=200
            )
            canvas_api_client._create_session()  # pylint: disable=protected-access

            with pytest.raises(ClientError) as client_error:
                canvas_api_client._handle_canvas_assignment_retrieval(  # pylint: disable=protected-access
                    'integration_id_1',
                    self.canvas_course_id,
                    'assignment_name'
                )

            assert client_error.value.message == 'Something went wrong retrieving assignments from Canvas. Got' \
                                                 ' response: {"error": "something went wrong"}'

    def test_grade_reporting_post_assignment_500s(self):
        """
        Test that the client raises the appropriate error if Canvas returns an error after the client posts an
        assignment.
        """
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET,
                self.canvas_assignment_url,
                json=[]
            )
            rsps.add(
                responses.POST,
                self.canvas_assignment_url,
                json={'errors': [{'message': 'The specified resource does not exist.'}]}
            )
            canvas_api_client = CanvasAPIClient(self.enterprise_config)

            # Creating a Canvas assignment will require the session to be created
            rsps.add(
                responses.POST,
                self.oauth_url,
                json=self._token_response(),
                status=200
            )
            canvas_api_client._create_session()  # pylint: disable=protected-access

            with pytest.raises(ClientError) as client_error:
                canvas_api_client._handle_canvas_assignment_retrieval(  # pylint: disable=protected-access
                    'integration_id_1',
                    self.canvas_course_id,
                    'assignment_name'
                )

            assert client_error.value.message == 'Something went wrong creating an assignment on Canvas. Got ' \
                                                 'response: {"errors": [{"message": "The specified resource does not ' \
                                                 'exist."}]}'

    def test_grade_reporting_post_submission_500s(self):
        """
        Test that the client raises the appropriate error if Canvas returns an error after the client posts grade data
        in the form of a Canvas submission.
        """
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.PUT,
                self.canvas_submission_url,
                json={'errors': [{'message': 'Something went wrong.'}]},
                status=400
            )
            canvas_api_client = CanvasAPIClient(self.enterprise_config)

            # Submitting a Canvas assignment will require the session to be created
            rsps.add(
                responses.POST,
                self.oauth_url,
                json=self._token_response(),
                status=200
            )
            canvas_api_client._create_session()  # pylint: disable=protected-access

            with pytest.raises(ClientError) as client_error:
                canvas_api_client._handle_canvas_assignment_submission(  # pylint: disable=protected-access
                    '100',
                    self.canvas_course_id,
                    self.canvas_assignment_id,
                    self.canvas_user_id
                )
            assert client_error.value.message == (
                'Something went wrong while posting a submission to Canvas '
                'assignment: {} under Canvas course: {}. Recieved response '
                '{{"errors": [{{"message": "Something went wrong."}}]}} with the '
                'status code: 400'
            ).format(
                str(self.canvas_assignment_id),
                str(self.canvas_course_id)
            )

    def test_create_client_session_with_oauth_access_key(self):
        """ Test instantiating the client will fetch and set the session's oauth access key"""
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.POST,
                self.oauth_url,
                json=self._token_response(),
                status=200
            )
            successful_canvas_api_client = CanvasAPIClient(self.enterprise_config)
            assert successful_canvas_api_client.expires_at is None
            successful_canvas_api_client._create_session()  # pylint: disable=protected-access

            assert successful_canvas_api_client.session.headers["Authorization"] == "Bearer " + self.access_token
            assert successful_canvas_api_client.expires_at is not None

    def test_client_instantiation_fails_without_client_id(self):
        with pytest.raises(ClientError) as client_error:
            self.enterprise_config.client_id = None
            canvas_api_client = CanvasAPIClient(self.enterprise_config)
            canvas_api_client._create_session()  # pylint: disable=protected-access
        assert client_error.value.message == "Failed to generate oauth access token: Client ID required."

    def test_client_instantiation_fails_without_client_secret(self):
        with pytest.raises(ClientError) as client_error:
            self.enterprise_config.client_secret = None
            canvas_api_client = CanvasAPIClient(self.enterprise_config)
            canvas_api_client._create_session()  # pylint: disable=protected-access
        assert client_error.value.message == "Failed to generate oauth access token: Client secret required."

    def test_client_instantiation_fails_without_refresh_token(self):
        with pytest.raises(ClientError) as client_error:
            self.enterprise_config.refresh_token = None
            canvas_api_client = CanvasAPIClient(self.enterprise_config)
            canvas_api_client._create_session()  # pylint: disable=protected-access
        assert client_error.value.message == "Failed to generate oauth access token: Refresh token required."

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
                json=self._token_response(),
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
                json=self._token_response(),
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
                json=self._token_response(),
                status=200
            )
            request_mock.add(
                responses.PUT,
                self.update_url + str(course_id),
                body=b'Mock update response text'
            )
            canvas_api_client.update_content_metadata(course_to_update)

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
                    json=self._token_response(),
                    status=200
                )
                transmitter_method = getattr(canvas_api_client, request_type)
                transmitter_method(poorly_formatted_data)

        assert client_error.value.message == 'Unable to decode data.'

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
                    json=self._token_response(),
                    status=200
                )
                transmitter_method = getattr(canvas_api_client, request_type)
                transmitter_method(bad_course_to_update)

        assert client_error.value.message == 'Could not transmit data, no integration ID present.'

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
                    json=self._token_response(),
                    status=200
                )
                transmitter_method = getattr(canvas_api_client, request_type)
                transmitter_method(course_to_update)

        assert client_error.value.message == 'No Canvas courses found with associated integration ID: {}.'.format(
            self.integration_id
        )

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
                    json=self._token_response(),
                    status=200
                )
                transmitter_method = getattr(canvas_api_client, request_type)
                transmitter_method(empty_data)

        assert client_error.value.message == 'No data to transmit.'
