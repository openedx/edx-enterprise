"""
Tests for clients in integrated_channels.
"""

import random
import unittest
from urllib.parse import urljoin

import pytest
import responses
from requests.models import Response

from integrated_channels.exceptions import ClientError
from integrated_channels.moodle.client import MoodleAPIClient, MoodleClientError
from test_utils import factories

SERIALIZED_DATA = {
    'courses[0][summary]': 'edX Demonstration Course',
    'courses[0][shortname]': 'edX Demonstration Course (edX+DemoX)',
    'courses[0][idnumber]': 'edX+DemoX',
    'courses[0][startdate]': '2030-01-01T00:00:00Z',
    'courses[0][enddate]': '2030-03-01T00:00:00Z',
}

MULTI_SERIALIZED_DATA = {
    'courses[0][summary]': 'edX Demonstration Course',
    'courses[0][shortname]': 'edX Demonstration Course (edX+DemoX)',
    'courses[0][idnumber]': 'edX+DemoX',
    'courses[0][startdate]': '2030-01-01T00:00:00Z',
    'courses[0][enddate]': '2030-03-01T00:00:00Z',
    'courses[1][summary]': 'edX Demonstration Course 2',
    'courses[1][shortname]': 'edX Demonstration Course 2 (edX+DemoX)',
    'courses[1][idnumber]': 'edX+DemoX2',
    'courses[1][startdate]': '2030-01-01T00:00:00Z',
    'courses[1][enddate]': '2030-03-01T00:00:00Z',
}

SUCCESSFUL_RESPONSE = unittest.mock.Mock(spec=Response)
SUCCESSFUL_RESPONSE.json.return_value = {}
SUCCESSFUL_RESPONSE.status_code = 200


SHORTNAMETAKEN_RESPONSE = unittest.mock.Mock(spec=Response)
SHORTNAMETAKEN_RESPONSE.json.return_value = {
    'errorcode': 'shortnametaken',
    'message': 'Short name is already used for another course (edX Demonstration Course (edX+DemoX))',
}
SHORTNAMETAKEN_RESPONSE.status_code = 200

COURSEIDNUMBERTAKEN_RESPONSE = unittest.mock.Mock(spec=Response)
COURSEIDNUMBERTAKEN_RESPONSE.json.return_value = {
    'errorcode': 'courseidnumbertaken',
    'message': 'ID number is already used for another course (edX Demonstration Course (edX+DemoX))',
}
COURSEIDNUMBERTAKEN_RESPONSE.status_code = 200


@pytest.mark.django_db
class TestMoodleApiClient(unittest.TestCase):
    """
    Test Moodle API client methods.
    """

    def setUp(self):
        super().setUp()
        self.moodle_base_url = 'http://testing/'
        self.token = 'token'
        self.password = 'pass'
        self.user = 'user'
        self.user_email = 'testemail@example.com'
        self.moodle_api_path = '/webservice/rest/server.php'
        self.moodle_course_id = random.randint(1, 1000)
        self._get_courses_response = bytearray('{{"courses": [{{"id": {}}}]}}'.format(self.moodle_course_id), 'utf-8')
        self.empty_get_courses_response = bytearray('{"courses": []}', 'utf-8')
        self.moodle_module_id = random.randint(1, 1000)
        self.moodle_module_name = 'module'
        self.moodle_user_id = random.randint(1, 1000)
        self.grade = round(random.uniform(0, 1), 2)
        self.learner_data_payload = '{{"courseID": {}, "grade": {}}}'.format(self.moodle_course_id, self.grade)
        self.enterprise_config = factories.MoodleEnterpriseCustomerConfigurationFactory(
            moodle_base_url=self.moodle_base_url,
            username=self.user,
            password=self.password,
            token=self.token,
        )

    def test_moodle_config_is_set(self):
        """
        Test global_moodle_config is setup.
        """
        moodle_api_client = MoodleAPIClient(self.enterprise_config)
        assert moodle_api_client.config is not None

    @responses.activate
    def test_get_course_id(self):
        """
        Test parsing of response from get_course_by_field Moodle endpoint.
        """
        client = MoodleAPIClient(self.enterprise_config)
        responses.add(
            responses.GET,
            urljoin(self.enterprise_config.moodle_base_url, self.moodle_api_path),
            json={'courses': [{'id': 2}]},
            status=200
        )
        assert client.get_course_id('course:test_course') == 2

    def test_successful_create_content_metadata(self):
        """
        Test core logic of create_content_metadata to ensure
        query string we send to Moodle is formatted correctly.
        """
        expected_data = SERIALIZED_DATA.copy()
        expected_data['wsfunction'] = 'core_course_create_courses'

        client = MoodleAPIClient(self.enterprise_config)
        client._post = unittest.mock.MagicMock(name='_post', return_value=SUCCESSFUL_RESPONSE)  # pylint: disable=protected-access
        client.create_content_metadata(SERIALIZED_DATA)
        client._post.assert_called_once_with(expected_data)  # pylint: disable=protected-access

    def test_duplicate_shortname_create_content_metadata(self):
        """
        Test core logic of create_content_metadata when a duplicate exists
        to ensure we handle it properly when only sending a single (treat as success).
        """
        expected_data = SERIALIZED_DATA.copy()
        expected_data['wsfunction'] = 'core_course_create_courses'

        client = MoodleAPIClient(self.enterprise_config)
        client._post = unittest.mock.MagicMock(name='_post', return_value=SHORTNAMETAKEN_RESPONSE)  # pylint: disable=protected-access
        client.create_content_metadata(SERIALIZED_DATA)
        client._post.assert_called_once_with(expected_data)  # pylint: disable=protected-access

    def test_duplicate_courseidnumber_create_content_metadata(self):
        """
        Test core logic of create_content_metadata when a duplicate exists
        to ensure we handle it properly when only sending a single (treat as success).
        """
        expected_data = SERIALIZED_DATA.copy()
        expected_data['wsfunction'] = 'core_course_create_courses'

        client = MoodleAPIClient(self.enterprise_config)
        client._post = unittest.mock.MagicMock(name='_post', return_value=COURSEIDNUMBERTAKEN_RESPONSE)  # pylint: disable=protected-access
        client.create_content_metadata(SERIALIZED_DATA)
        client._post.assert_called_once_with(expected_data)  # pylint: disable=protected-access

    def test_multi_duplicate_create_content_metadata(self):
        """
        Test core logic of create_content_metadata when a duplicate exists
        to ensure we handle it properly when sending more than one course (throw exception).
        """
        expected_data = MULTI_SERIALIZED_DATA.copy()
        expected_data['wsfunction'] = 'core_course_create_courses'

        client = MoodleAPIClient(self.enterprise_config)
        client._post = unittest.mock.MagicMock(name='_post', return_value=SHORTNAMETAKEN_RESPONSE)  # pylint: disable=protected-access
        with self.assertRaises(MoodleClientError):
            client.create_content_metadata(MULTI_SERIALIZED_DATA)
        client._post.assert_called_once_with(expected_data)  # pylint: disable=protected-access

    def test_multi_duplicate_courseidnumber_create_content_metadata(self):
        """
        Test core logic of create_content_metadata when a duplicate exists
        to ensure we handle it properly when sending more than one course (throw exception).
        """
        expected_data = MULTI_SERIALIZED_DATA.copy()
        expected_data['wsfunction'] = 'core_course_create_courses'

        client = MoodleAPIClient(self.enterprise_config)
        client._post = unittest.mock.MagicMock(name='_post', return_value=COURSEIDNUMBERTAKEN_RESPONSE)  # pylint: disable=protected-access
        with self.assertRaises(MoodleClientError):
            client.create_content_metadata(MULTI_SERIALIZED_DATA)
        client._post.assert_called_once_with(expected_data)  # pylint: disable=protected-access

    def test_update_content_metadata(self):
        """
        Test core logic of update_content_metadata to ensure
        query string we send to Moodle is formatted correctly.
        """
        expected_data = SERIALIZED_DATA.copy()
        expected_data['courses[0][id]'] = self.moodle_course_id
        expected_data['wsfunction'] = 'core_course_update_courses'

        client = MoodleAPIClient(self.enterprise_config)
        client._post = unittest.mock.MagicMock(name='_post', return_value=SUCCESSFUL_RESPONSE)  # pylint: disable=protected-access
        client._get_course_id = unittest.mock.MagicMock(name='_get_course_id')  # pylint: disable=protected-access
        client._get_course_id.return_value = self.moodle_course_id  # pylint: disable=protected-access
        client.update_content_metadata(SERIALIZED_DATA)
        client._post.assert_called_once_with(expected_data)  # pylint: disable=protected-access

    def test_delete_content_metadata(self):
        """
        Test core logic for formatting a delete request to Moodle.
        """
        expected_data = {'wsfunction': 'core_course_delete_courses', 'courseids[]': self.moodle_course_id}

        client = MoodleAPIClient(self.enterprise_config)
        client._post = unittest.mock.MagicMock(name='_post', return_value=SUCCESSFUL_RESPONSE)  # pylint: disable=protected-access
        client._get_courses = unittest.mock.MagicMock(name='_get_courses')  # pylint: disable=protected-access

        mock_response = Response()
        mock_response.status_code = 200
        mock_response._content = self._get_courses_response  # pylint: disable=protected-access

        client._get_courses.return_value = mock_response  # pylint: disable=protected-access
        client.delete_content_metadata(SERIALIZED_DATA)

        client._post.assert_called_once_with(expected_data)  # pylint: disable=protected-access

    def test_delete_content_metadata_no_course_found(self):
        """
        Test that we do not fail on delete when a course is not found on Canvas.
        """
        client = MoodleAPIClient(self.enterprise_config)
        client._post = unittest.mock.MagicMock(name='_post', return_value=SUCCESSFUL_RESPONSE)  # pylint: disable=protected-access
        client._get_courses = unittest.mock.MagicMock(name='_get_courses')  # pylint: disable=protected-access

        mock_response = Response()
        mock_response.status_code = 200
        mock_response._content = self.empty_get_courses_response  # pylint: disable=protected-access
        client._get_courses.return_value = mock_response  # pylint: disable=protected-access
        result = client.delete_content_metadata(SERIALIZED_DATA)
        assert result.json() == {"result": "Course not found."}

    def test_course_completion_with_no_course(self):
        """Test that we properly raise exceptions if the client receives a 404 from Moodle"""
        with responses.RequestsMock() as rsps:
            moodle_api_path = urljoin(
                self.enterprise_config.moodle_base_url,
                self.moodle_api_path,
            )
            moodle_get_courses_query = 'wstoken={}&wsfunction=core_course_get_courses_by_field&field=idnumber' \
                                       '&value={}&moodlewsrestformat=json'.format(self.token, self.moodle_course_id)
            request_url = '{}?{}'.format(moodle_api_path, moodle_get_courses_query)
            rsps.add(
                responses.GET,
                request_url,
                body=b'{}',
                status=200
            )
            client = MoodleAPIClient(self.enterprise_config)
            with pytest.raises(ClientError) as client_error:
                client.create_course_completion(self.user_email, self.learner_data_payload)

            assert client_error.value.message == 'MoodleAPIClient request failed: 404 ' \
                                                 'Course key "{}" not found in Moodle.'.format(self.moodle_course_id)

    def test_client_behavior_on_successful_learner_data_transmission(self):
        """
        Test that given successful requests for moodle learner data,
        the client makes the appropriate _post call to update a user's grade
        """
        client = MoodleAPIClient(self.enterprise_config)
        client._post = unittest.mock.MagicMock(name='_post', return_value=SUCCESSFUL_RESPONSE)  # pylint: disable=protected-access

        client.get_course_id = unittest.mock.MagicMock(name='_get_course_id')
        client.get_course_id.return_value = self.moodle_course_id

        client.get_course_final_grade_module = unittest.mock.MagicMock(name='_get_final_grade_module')
        client.get_course_final_grade_module.return_value = self.moodle_module_id, self.moodle_module_name

        client.get_creds_of_user_in_course = unittest.mock.MagicMock(name='get_user_in_course')
        client.get_creds_of_user_in_course.return_value = self.moodle_user_id

        # The base transmitter expects the create course completion response to be a tuple of (code, body)
        assert client.create_course_completion(self.user_email, self.learner_data_payload) == (
            SUCCESSFUL_RESPONSE.status_code,
            SUCCESSFUL_RESPONSE.text
        )

        expected_params = {
            'wsfunction': 'core_grades_update_grades',
            'source': self.moodle_module_name,
            'courseid': self.moodle_course_id,
            'component': 'mod_assign',
            'activityid': self.moodle_module_id,
            'itemnumber': 0,
            'grades[0][studentid]': self.moodle_user_id,
            'grades[0][grade]': self.grade * 100
        }

        client._post.assert_called_once_with(expected_params)  # pylint: disable=protected-access
