"""
Tests for clients in integrated_channels.
"""

import datetime
import json
import random
import unittest
from unittest import mock
from urllib.parse import urljoin

import pytest
import responses
from freezegun import freeze_time
from requests.models import Response

from django.utils import timezone

from integrated_channels.canvas.client import MESSAGE_WHEN_COURSE_WAS_DELETED, CanvasAPIClient
from integrated_channels.canvas.utils import CanvasUtil
from integrated_channels.exceptions import ClientError
from integrated_channels.integrated_channel.client import IntegratedChannelHealthStatus
from test_utils import factories

NOW = datetime.datetime(2017, 1, 2, 3, 4, 5, tzinfo=datetime.timezone.utc)
NOW_TIMESTAMP_FORMATTED = NOW.strftime('%F')


def _raise_ClientError(*unused_args):
    raise ClientError('Test Exception')


@pytest.mark.django_db
class TestCanvasApiClient(unittest.TestCase):
    """
    Test Canvas API client methods.
    """

    def setUp(self):
        super().setUp()
        self.account_id = random.randint(9223372036854775800, 9223372036854775807)
        self.canvas_email = "test@test.com"
        self.canvas_user_id = random.randint(1, 1000)
        self.canvas_course_id = random.randint(1, 1000)
        self.canvas_course_id_2 = random.randint(1001, 2000)
        self.canvas_assignment_id = random.randint(1, 1000)
        self.canvas_assignment_id_2 = random.randint(1001, 2000)
        self.canvas_assignment_id_3 = random.randint(2001, 3000)
        self.course_id = "edx+111"
        self.course_id_2 = "edx+222"
        self.subsection_id = "subsection:123"
        self.subsection_id_2 = "subsection:456"
        self.subsection_name = 'subsection 1'
        self.points_possible = random.randint(1, 100)
        self.points_earned = self.points_possible - 1
        self.grade = self.points_earned / float(self.points_possible)
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
        self.canvas_assignment_2_url = \
            "{base}/api/v1/courses/{course_id}/assignments".format(
                base=self.url_base,
                course_id=self.canvas_course_id_2,
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
        self.integration_id_2 = 'course-v2:{course_id}+2T2020'.format(course_id=self.course_id)
        self.integration_id_3 = 'course-v3:{course_id}+2T2020'.format(course_id=self.course_id)
        self.integration_id_4 = 'course-v4:{course_id}+2T2020'.format(course_id=self.course_id)

        self.course_completion_date = datetime.date(
            2020,
            random.randint(1, 10),
            random.randint(1, 10)
        )
        self.completion_level_payload = \
            '{{"completedTimestamp": "{completion_date}", "courseCompleted": "true", '\
            '"courseID": "{course_id}", "grade": "{course_grade}", "userID": "{email}"}}'.format(
                completion_date=self.course_completion_date,
                course_id=self.course_id,
                email=self.canvas_email,
                course_grade=self.grade
            )
        self.assessment_level_payload = \
            '{{"courseID": "{course_id}", "points_possible": "{points_possible}", "points_earned": "{points_earned}",' \
            ' "subsectionID": "{subsectionID}", "subsection_name": "{subsection_name}", "userID": "{email}", "grade":' \
            ' "{grade}"}}'.format(
                course_id=self.course_id,
                email=self.canvas_email,
                points_possible=self.points_possible,
                points_earned=self.points_earned,
                subsectionID=self.subsection_id,
                subsection_name=self.subsection_name,
                grade=self.grade
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
        """
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET,
                self.canvas_user_courses_url,
                json=[]
            )

            # Creating a Canvas assignment will require the session to be created
            rsps.add(
                responses.POST,
                self.oauth_url,
                json=self._token_response(),
                status=200
            )

            canvas_api_client = CanvasAPIClient(self.enterprise_config)
            canvas_api_client._create_session()  # pylint: disable=protected-access

            with pytest.raises(ClientError) as client_error:
                canvas_api_client._handle_get_user_canvas_course(self.canvas_user_id, self.course_id)  # pylint: disable=protected-access
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
            assignment_not_found_headers = {
                'Link': (
                    '<{assignment_url}?page=1&per_page=10>; rel="current",'
                    '<{assignment_url}?page=1&per_page=10>; rel="prev",'
                    '<{assignment_url}?page=1&per_page=10>; rel="first",'
                    '<{assignment_url}?page=1&per_page=10>; rel="last"'.format(
                        assignment_url=self.canvas_course_assignments_url
                    )
                )
            }
            rsps.add(
                responses.GET,
                self.canvas_assignment_url,
                json=[],
                headers=assignment_not_found_headers
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

    def test_assessment_level_reporting_omits_from_final_grade(self):
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.POST,
                self.oauth_url,
                json=self._token_response(),
                status=200
            )
            canvas_api_client = CanvasAPIClient(self.enterprise_config)
            canvas_api_client._create_session()  # pylint: disable=protected-access

            canvas_api_client._search_for_canvas_user_by_email = unittest.mock.MagicMock(  # pylint: disable=protected-access
                return_value=self.canvas_user_id
            )
            canvas_api_client._handle_get_user_canvas_course = unittest.mock.MagicMock(  # pylint: disable=protected-access
                return_value=self.canvas_course_id
            )
            canvas_api_client._handle_canvas_assignment_retrieval = unittest.mock.MagicMock(  # pylint: disable=protected-access
                return_value=self.canvas_assignment_id,
                name='_handle_canvas_assignment_retrieval'
            )
            mocked_response = unittest.mock.Mock(spec=Response)
            mocked_response.json.return_value = {}
            mocked_response.status_code = 200
            canvas_api_client._handle_canvas_assignment_submission = unittest.mock.MagicMock(  # pylint: disable=protected-access
                return_value=mocked_response
            )

            canvas_api_client.create_assessment_reporting(self.canvas_email, self.assessment_level_payload)
            assert canvas_api_client._handle_canvas_assignment_retrieval.mock_calls[0].kwargs[  # pylint: disable=protected-access
                'is_assessment_grade'
            ]

    def test_completion_level_reporting_included_in_final_grade(self):
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.POST,
                self.oauth_url,
                json=self._token_response(),
                status=200
            )
            canvas_api_client = CanvasAPIClient(self.enterprise_config)
            canvas_api_client._create_session()  # pylint: disable=protected-access

            canvas_api_client._search_for_canvas_user_by_email = unittest.mock.MagicMock(  # pylint: disable=protected-access
                return_value=self.canvas_user_id
            )
            canvas_api_client._handle_get_user_canvas_course = unittest.mock.MagicMock(  # pylint: disable=protected-access
                return_value=self.canvas_course_id
            )
            canvas_api_client._handle_canvas_assignment_retrieval = unittest.mock.MagicMock(  # pylint: disable=protected-access
                return_value=self.canvas_assignment_id,
                name='_handle_canvas_assignment_retrieval'
            )
            mocked_response = unittest.mock.Mock(spec=Response)
            mocked_response.json.return_value = {}
            mocked_response.status_code = 200
            canvas_api_client._handle_canvas_assignment_submission = unittest.mock.MagicMock(  # pylint: disable=protected-access
                return_value=mocked_response
            )

            canvas_api_client.create_course_completion(self.canvas_email, self.assessment_level_payload)
            assert not canvas_api_client._handle_canvas_assignment_retrieval.mock_calls[0].kwargs.get(  # pylint: disable=protected-access
                'is_assessment_grade'
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

    @mock.patch.object(CanvasUtil, 'find_course_by_course_id')
    def test_create_course_success(self, mock_find_course_by_course_id):
        # because we don't want an existing course to be found in this case
        mock_find_course_by_course_id.return_value = None

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
                CanvasUtil.course_create_endpoint(self.enterprise_config),
                status=201,
                body=expected_resp
            )
            status_code, response_text = canvas_api_client.create_content_metadata(course_to_create)
            assert status_code == 201
            assert response_text == expected_resp

    @mock.patch.object(CanvasUtil, 'find_course_by_course_id')
    def test_existing_course_is_updated_instead(self, mock_find_course_by_course_id):
        # to simulate finding an existing course with workflow_state != 'deleted'
        mock_find_course_by_course_id.return_value = {
            'workflow_state': 'unpublished',
            'id': 111,
            'name': 'course already exists!',
        }

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
                responses.PUT,
                CanvasUtil.course_update_endpoint(self.enterprise_config, 111),
                status=201,
                body=expected_resp
            )
            status_code, response_text = canvas_api_client.create_content_metadata(course_to_create)
            assert status_code == 201
            assert response_text == expected_resp

    @mock.patch.object(CanvasUtil, 'find_course_by_course_id')
    def test_existing_course_is_ignored_if_deleted(self, mock_find_course_by_course_id):
        # to simulate finding an existing course with workflow_state == 'deleted'
        mock_find_course_by_course_id.return_value = {
            'workflow_state': 'deleted',
            'id': 111,
            'name': 'course already deleted in Canvas!',
        }

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

            status_code, response_text = canvas_api_client.create_content_metadata(course_to_create)
            assert status_code == 200
            assert response_text == MESSAGE_WHEN_COURSE_WAS_DELETED

    def test_assignment_retrieval_pagination(self):
        """
        Test that the Canvas client properly re-requests the next available page (if there exists one) If the
        assignment ID is not found within the response.
        """
        # Test json blobs have been shortened-
        # Course assignment responses and headers normally contain more data than just the integration ID and Link
        paginated_assignment_response_1 = [
            {'integration_id': self.integration_id, 'id': 1},
            {'integration_id': self.integration_id_2, 'id': 2}
        ]
        paginated_assignment_headers_1 = {
            'Link': (
                '<{assignment_url}?page=2&per_page=10>; rel="current",'
                '<{assignment_url}?page=1&per_page=10>; rel="prev",'
                '<{assignment_url}?page=1&per_page=10>; rel="first",'
                '<{assignment_url}?page=2&per_page=10>; rel="last"'.format(
                    assignment_url=self.canvas_course_assignments_url
                )
            )
        }
        paginated_assignment_response_2 = [
            {'integration_id': self.integration_id_3, 'id': 3},
            {'integration_id': self.integration_id_4, 'id': 4}
        ]
        paginated_assignment_headers_2 = {
            'Link': (
                '<{assignment_url}?page=1&per_page=10>; rel="current",'
                '<{assignment_url}?page=2&per_page=10>; rel="next",'
                '<{assignment_url}?page=1&per_page=10>; rel="first",'
                '<{assignment_url}?page=2&per_page=10>; rel="last"'.format(
                    assignment_url=self.canvas_course_assignments_url
                )
            )
        }
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.POST,
                self.oauth_url,
                json=self._token_response(),
                status=200
            )
            rsps.add(
                responses.GET,
                self.canvas_assignment_url,
                json=paginated_assignment_response_2,
                status=200,
                headers=paginated_assignment_headers_2
            )
            rsps.add(
                responses.GET,
                '{}?page=2&per_page=10'.format(self.canvas_course_assignments_url),
                json=paginated_assignment_response_1,
                status=200,
                headers=paginated_assignment_headers_1
            )
            canvas_api_client = CanvasAPIClient(self.enterprise_config)
            canvas_api_client._create_session()  # pylint: disable=protected-access
            canvas_assignment = canvas_api_client._handle_canvas_assignment_retrieval(  # pylint: disable=protected-access
                self.integration_id,
                self.canvas_course_id,
                'Test Assignment'
            )

            assert canvas_assignment == 1

    @mock.patch.object(CanvasUtil, 'find_course_by_course_id')
    def test_successful_assignment_dedup(self, mock_find_course_by_course_id):
        """
        Test successful assignment dedup task removing duplicate assignments from multiple courses
        """
        mock_find_course_by_course_id.side_effect = [{'id': self.canvas_course_id}, {'id': self.canvas_course_id_2}]
        canvas_api_client = CanvasAPIClient(self.enterprise_config)
        canvas_api_client._bulk_remove_course_assignments = mock.MagicMock(  # pylint: disable=protected-access
            side_effect=[
                ([self.canvas_assignment_id], []),
                ([self.canvas_assignment_id_2, self.canvas_assignment_id_3], [])
            ]
        )
        last_updated_1 = str(datetime.datetime(2020, 5, 17, 10))
        last_updated_2 = str(datetime.datetime(2020, 5, 17, 12))
        last_updated_3 = str(datetime.datetime(2020, 5, 17, 14))

        with responses.RequestsMock() as request_mock:
            request_mock.add(
                responses.POST,
                self.oauth_url,
                json=self._token_response(),
                status=200
            )

            paginated_assignment_headers_1 = {
                'Link': (
                    '<{assignment_url}?page=1&per_page=10>; rel="current",'
                    '<{assignment_url}?page=1&per_page=10>; rel="first",'
                    '<{assignment_url}?page=1&per_page=10>; rel="last"'.format(
                        assignment_url=self.canvas_course_assignments_url
                    )
                )
            }
            request_mock.add(
                responses.GET,
                self.canvas_assignment_url,
                json=[{
                    'id': self.canvas_assignment_id,
                    'integration_id': self.subsection_id,
                    'updated_at': last_updated_1
                }, {
                    'id': self.canvas_assignment_id_2,
                    'integration_id': self.subsection_id,
                    'updated_at': last_updated_2
                }],
                status=200,
                headers=paginated_assignment_headers_1
            )

            paginated_assignment_headers_2 = {
                'Link': (
                    '<{assignment_url}?page=1&per_page=10>; rel="current",'
                    '<{assignment_url}?page=1&per_page=10>; rel="first",'
                    '<{assignment_url}?page=1&per_page=10>; rel="last"'.format(
                        assignment_url=self.canvas_course_assignments_url
                    )
                )
            }
            request_mock.add(
                responses.GET,
                self.canvas_assignment_2_url,
                json=[{
                    'id': self.canvas_assignment_id,
                    'integration_id': self.subsection_id_2,
                    'updated_at': last_updated_1
                }, {
                    'id': self.canvas_assignment_id_2,
                    'integration_id': self.subsection_id_2,
                    'updated_at': last_updated_2
                }, {
                    'id': self.canvas_assignment_id_3,
                    'integration_id': self.subsection_id_2,
                    'updated_at': last_updated_3
                }],
                status=200,
                headers=paginated_assignment_headers_2
            )

            canvas_api_client._create_session()  # pylint: disable=protected-access
            code, body = canvas_api_client.cleanup_duplicate_assignment_records([self.course_id, self.course_id_2])

            assert code == 200
            assert body == "Removed 3 duplicate assignments from Canvas."

    @mock.patch.object(CanvasUtil, 'find_course_by_course_id')
    def test_assignment_dedup_partial_failure(self, mock_find_course_by_course_id):
        """
        Test assignment dedup task partially fails due to not finding one course
        """
        mock_find_course_by_course_id.side_effect = [{'id': self.canvas_course_id}, None]
        canvas_api_client = CanvasAPIClient(self.enterprise_config)
        canvas_api_client._bulk_remove_course_assignments = mock.MagicMock(  # pylint: disable=protected-access
            return_value=([self.canvas_assignment_id], [])
        )
        last_updated_1 = str(datetime.datetime(2020, 5, 17, 10))
        last_updated_2 = str(datetime.datetime(2020, 5, 17, 12))

        with responses.RequestsMock() as request_mock:
            request_mock.add(
                responses.POST,
                self.oauth_url,
                json=self._token_response(),
                status=200
            )
            paginated_assignment_headers = {
                'Link': (
                    '<{assignment_url}?page=1&per_page=10>; rel="current",'
                    '<{assignment_url}?page=1&per_page=10>; rel="first",'
                    '<{assignment_url}?page=1&per_page=10>; rel="last"'.format(
                        assignment_url=self.canvas_course_assignments_url
                    )
                )
            }

            request_mock.add(
                responses.GET,
                self.canvas_assignment_url,
                json=[{
                    'id': self.canvas_assignment_id,
                    'integration_id': self.subsection_id,
                    'updated_at': last_updated_1
                }, {
                    'id': self.canvas_assignment_id_2,
                    'integration_id': self.subsection_id,
                    'updated_at': last_updated_2
                }],
                status=200,
                headers=paginated_assignment_headers
            )
            canvas_api_client._create_session()  # pylint: disable=protected-access
            code, body = canvas_api_client.cleanup_duplicate_assignment_records([self.course_id, self.course_id_2])
            assert code == 400
            assert body == (
                "Failed to dedup all assignments for the following courses: ['{}']. Number of individual assignments "
                "that failed to be deleted: 0. Total assignments removed: 1.".format(
                    self.course_id_2
                )
            )

    def test_parsing_next_paginated_endpoint(self):
        """
        Test that the _determine_next_results_page method properly determines the next url of paginated result when
        present.
        """
        canvas_api_response = Response()
        canvas_api_response.headers = {
            'Link': '<canvas.com?page=1&per_page=10>; rel="current",'
                    '<canvas.com?page=2&per_page=10>; rel="next",'
                    '<canvas.com?page=1&per_page=10>; rel="first",'
                    '<canvas.com?page=2&per_page=10>; rel="last"'
        }
        next_page = CanvasUtil.determine_next_results_page(canvas_api_response)
        assert next_page == 'canvas.com?page=2&per_page=10'

    def test_parsing_end_of_paginated_results(self):
        """
        Test that the _determine_next_results_page returns False if there are no more pages of results.
        """
        canvas_api_response = Response()
        canvas_api_response.headers = {
            'Link': '<canvas.com?page=2&per_page=10>; rel="current",'
                    '<canvas.com?page=1&per_page=10>; rel="prev",'
                    '<canvas.com?page=1&per_page=10>; rel="first",'
                    '<canvas.com?page=2&per_page=10>; rel="last"'
        }
        next_page = CanvasUtil.determine_next_results_page(canvas_api_response)
        assert not next_page

    def test_parse_unique_newest_assignments_removes_older_assignments(self):
        """
        Test that _parse_unique_newest_assignments will ingest Canvas assignment responses and will replace older
        duplicate assignments in `current_assignments` with more recent ones.
        """
        canvas_api_client = CanvasAPIClient(self.enterprise_config)

        integration_id_1 = 'edX+816'
        integration_id_2 = 'edX+100'

        newer_canvas_assignment_id_1 = 10
        newer_canvas_assignment_id_2 = 11
        older_canvas_assignment_id_1 = 12
        older_canvas_assignment_id_2 = 13

        current_assignments = {
            integration_id_1: {
                'id': older_canvas_assignment_id_1,
                'updated_at': '2021-06-10T13:57:19Z',
            },
            integration_id_2: {
                'id': older_canvas_assignment_id_2,
                'updated_at': '2021-06-10T13:58:19Z',
            }
        }
        assignments_to_delete = []
        assignment_response_json = [{
            'integration_id': integration_id_1,
            'id': newer_canvas_assignment_id_1,
            'updated_at': '2021-06-11T13:57:19Z'
        }, {
            'integration_id': integration_id_2,
            'id': newer_canvas_assignment_id_2,
            'updated_at': '2021-06-11T13:58:19Z'
        }]

        current_assignments, assignments_to_delete = canvas_api_client._parse_unique_newest_assignments(  # pylint: disable=protected-access
            current_assignments,
            assignments_to_delete,
            assignment_response_json
        )
        assert current_assignments[integration_id_1]['id'] == newer_canvas_assignment_id_1
        assert current_assignments[integration_id_2]['id'] == newer_canvas_assignment_id_2

    def test_successful_bulk_remove_course_assignments(self):
        """
        Test a successful run of deduplication assignments
        """
        canvas_api_client = CanvasAPIClient(self.enterprise_config)
        with responses.RequestsMock() as request_mock:
            request_mock.add(
                responses.DELETE,
                self.canvas_assignment_url + '/{}'.format(self.canvas_assignment_id),
                json={},
                status=200
            )
            request_mock.add(
                responses.DELETE,
                self.canvas_assignment_url + '/{}'.format(self.canvas_assignment_id_2),
                json={},
                status=200
            )
            request_mock.add(
                responses.POST,
                self.oauth_url,
                json=self._token_response(),
                status=200
            )
            canvas_api_client._create_session()  # pylint: disable=protected-access
            assignments_removed, [] = canvas_api_client._bulk_remove_course_assignments(  # pylint: disable=protected-access
                self.canvas_course_id,
                [self.canvas_assignment_id, self.canvas_assignment_id_2]
            )

            assert len(assignments_removed) == 2
            assert self.canvas_assignment_id_2 in assignments_removed
            assert self.canvas_assignment_id in assignments_removed

    def test_bulk_remove_course_assignments_partial_failure(self):
        """
        Test client behaviors when a course is not found a deduplication of assessments task
        """
        canvas_api_client = CanvasAPIClient(self.enterprise_config)
        with responses.RequestsMock() as request_mock:
            request_mock.add(
                responses.DELETE,
                self.canvas_assignment_url + '/{}'.format(self.canvas_assignment_id),
                json={'errors': [{'message': 'Something went wrong.'}]},
                status=500
            )
            request_mock.add(
                responses.DELETE,
                self.canvas_assignment_url + '/{}'.format(self.canvas_assignment_id_2),
                json={},
                status=200
            )
            request_mock.add(
                responses.POST,
                self.oauth_url,
                json=self._token_response(),
                status=200
            )
            canvas_api_client._create_session()  # pylint: disable=protected-access
            assignments_removed, failed_assignments = canvas_api_client._bulk_remove_course_assignments(  # pylint: disable=protected-access
                self.canvas_course_id,
                [self.canvas_assignment_id, self.canvas_assignment_id_2]
            )
            assert self.canvas_assignment_id in failed_assignments
            assert len(failed_assignments) == 1
            assert len(assignments_removed) == 1
            assert self.canvas_assignment_id_2 in assignments_removed

    @mock.patch.object(CanvasUtil, 'find_course_by_course_id')
    def test_create_course_success_with_image_url(self, mock_find_course_by_course_id):
        canvas_api_client = CanvasAPIClient(self.enterprise_config)
        course_to_create = json.dumps({
            "course": {
                "integration_id": self.integration_id,
                "name": "test_course_create",
                "image_url": "http://image.one/url.png"
            }
        }).encode('utf-8')

        # because we don't want an existing course to be found in this case
        mock_find_course_by_course_id.return_value = None

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
                CanvasUtil.course_create_endpoint(self.enterprise_config),
                status=201,
                body=expected_resp
            )
            request_mock.add(
                responses.PUT,
                CanvasUtil.course_update_endpoint(self.enterprise_config, 1111),
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

    @mock.patch.object(CanvasUtil, 'find_course_by_course_id')
    def test_course_delete_fails_when_course_id_not_found(self, mock_find_course_by_course_id):
        mock_find_course_by_course_id.return_value = None
        course_to_update = '{{"course": {{"integration_id": "{}", "name": "test_course"}}}}'.format(
            self.integration_id
        ).encode()
        canvas_api_client = CanvasAPIClient(self.enterprise_config)

        with pytest.raises(ClientError) as client_error:
            with responses.RequestsMock() as request_mock:
                request_mock.add(
                    responses.POST,
                    self.oauth_url,
                    json=self._token_response(),
                    status=200
                )
                canvas_api_client.delete_content_metadata(course_to_update)

        assert client_error.value.message == 'No Canvas courses found with associated edx course ID: {}.'.format(
            self.integration_id
        )

    @mock.patch.object(CanvasUtil, 'find_course_by_course_id')
    def test_course_update_creates_when_course_id_not_found(self, mock_find_course_by_course_id):
        # None here indicates no matching course is found
        # we are already testing logic for CanvasUtil separately
        mock_find_course_by_course_id.return_value = None
        course_to_update = '{{"course": {{"integration_id": "{}", "name": "test_course"}}}}'.format(
            self.integration_id
        ).encode()
        canvas_api_client = CanvasAPIClient(self.enterprise_config)

        with responses.RequestsMock() as request_mock:
            request_mock.add(
                responses.POST,
                self.oauth_url,
                json=self._token_response(),
                status=200
            )
            mocked_create_messaged = '{"id": 1, "message": "content was created!"}'
            request_mock.add(
                responses.POST,
                canvas_api_client.course_create_url,
                body=mocked_create_messaged,
                status=200
            )
            status, response = canvas_api_client.update_content_metadata(course_to_update)

        assert status == 200
        assert response == mocked_create_messaged

    @mock.patch.object(CanvasUtil, 'find_course_by_course_id')
    def test_dont_update_if_course_is_deleted(self, mock_find_course_by_course_id):
        # to simulate finding an existing course with workflow_state == 'deleted'
        mock_find_course_by_course_id.return_value = {
            'workflow_state': 'deleted',
            'id': 111,
            'name': 'course already deleted in Canvas!',
        }

        canvas_api_client = CanvasAPIClient(self.enterprise_config)
        course_to_update = json.dumps({
            "course": {
                "integration_id": self.integration_id,
                "name": "test_course_update"
            }
        }).encode()

        with responses.RequestsMock() as request_mock:
            request_mock.add(
                responses.POST,
                self.oauth_url,
                json=self._token_response(),
                status=200
            )

            status_code, response_text = canvas_api_client.update_content_metadata(course_to_update)
            assert status_code == 200
            assert response_text == MESSAGE_WHEN_COURSE_WAS_DELETED

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

    @mock.patch('integrated_channels.canvas.client.refresh_session_if_expired', lambda x: ('mock session', 30))
    def test_health_check_healthy(self):
        """
        Test the client health check with healthy status
        """
        canvas_api_client = CanvasAPIClient(self.enterprise_config)
        assert canvas_api_client.health_check() == IntegratedChannelHealthStatus.HEALTHY

    @mock.patch('integrated_channels.canvas.client.refresh_session_if_expired', lambda x: ('mock session', 30))
    def test_health_check_invalid_config(self):
        """
        Test the client health check with invalid config
        """
        bad_enterprise_config = factories.CanvasEnterpriseCustomerConfigurationFactory(
            client_id=self.client_id,
            client_secret=self.client_secret,
            canvas_account_id=self.account_id,
            canvas_base_url='Not a valid url',
            refresh_token=self.refresh_token,
        )
        canvas_api_client = CanvasAPIClient(bad_enterprise_config)
        assert canvas_api_client.health_check() == IntegratedChannelHealthStatus.INVALID_CONFIG

    @mock.patch('integrated_channels.canvas.client.refresh_session_if_expired', _raise_ClientError)
    def test_health_check_connection_failure(self):
        """
        Test the client health check with connection failure
        """
        canvas_api_client = CanvasAPIClient(self.enterprise_config)
        assert canvas_api_client.health_check() == IntegratedChannelHealthStatus.CONNECTION_FAILURE

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

        assert client_error.value.message == "Unable to decode data. Type of data was <class 'str'>"

    def update_fails_with_poorly_constructed_data(self, request_type):
        """
        Helper method to test error handling with poorly constructed data
        """
        bad_course_to_update = b'{"course": {"name": "test_course"}}'
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
