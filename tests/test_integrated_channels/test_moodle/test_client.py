# -*- coding: utf-8 -*-
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
from integrated_channels.moodle.client import ANNOUNCEMENT_POST_SUBJECT, MoodleAPIClient
from test_utils import factories

SERIALIZED_DATA = {
    'courses[0][summary]': 'edX Demonstration Course',
    'courses[0][shortname]': 'edX+DemoX',
    'courses[0][startdate]': '2030-01-01T00:00:00Z',
    'courses[0][enddate]': '2030-03-01T00:00:00Z',
    'courses[0][announcement]': '<h1>Header text. HTML verification.</h1>',
    'courses[0][format]': 'singleactivity'
}

# MOODLE_COURSE_ID = 100

SUCCESSFUL_RESPONSE = unittest.mock.Mock(spec=Response)
SUCCESSFUL_RESPONSE.json.return_value = {}
SUCCESSFUL_RESPONSE.status_code = 200


@pytest.mark.django_db
class TestMoodleApiClient(unittest.TestCase):
    """
    Test Moodle API client methods.
    """

    def setUp(self):
        super(TestMoodleApiClient, self).setUp()
        self.moodle_base_url = 'http://testing'
        self.token = 'token'
        self.password = 'pass'
        self.user = 'user'
        self.user_email = 'testemail@example.com'
        self.moodle_api_path = '/webservice/rest/server.php'
        self.moodle_course_id = random.randint(1, 1000)
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

    def test_get_announcement_post(self):
        """
        Test get_announcement_post returns post id properly.
        """
        client = MoodleAPIClient(self.enterprise_config)
        forum_id = 1
        forum_post_id = 2  # arbitrary. I'm using "2" to differentiate it from the forum id.
        with responses.RequestsMock() as rsps:
            moodle_api_path = urljoin(
                self.enterprise_config.moodle_base_url,
                self.moodle_api_path,
            )
            moodle_discussion_query = 'wstoken={}&moodlewsrestformat=json' \
                                      '&wsfunction=mod_forum_get_forum_discussions&forumid={}' \
                                      .format(self.token, forum_id)
            request_url = '{}?{}'.format(moodle_api_path, moodle_discussion_query)
            rsps.add(
                responses.POST,
                request_url,
                json={"discussions": [{"subject": ANNOUNCEMENT_POST_SUBJECT, "id": forum_post_id}]},
                status=200
            )
            assert client.get_announcement_post(forum_id) == forum_post_id

    def test_create_content_metadata(self):
        """
        Test failure modes during content creation steps
        - This is more useful with the many failure modes and all the mocking we have to do here.
        """
        expected_data = SERIALIZED_DATA.copy()
        expected_data['wsfunction'] = 'core_course_create_courses'
        serialize_copy = SERIALIZED_DATA.copy()

        client = MoodleAPIClient(self.enterprise_config)

        client._wrapped_create_content_metadata = unittest.mock.MagicMock(  # pylint: disable=protected-access
            name='_wrapped_create_content_metadata'
        )
        client._wrapped_create_content_metadata.return_value = [{'warnings': ['']}]  # pylint: disable=protected-access
        with pytest.raises(ClientError) as client_error:
            client.create_content_metadata(SERIALIZED_DATA)

        assert client_error.value.message == 'Moodle Client Content Metadata Creation ' \
                                             'failed to create course {}'.format(
                                                 expected_data['courses[0][shortname]'])

        client._wrapped_create_content_metadata.return_value = [{'id': 1, 'shortname': 'edX+DemoX'}]  # pylint: disable=protected-access
        forum_post_response = unittest.mock.Mock(spec=Response)
        forum_post_response.json.return_value = {'warnings': ['stuff happened']}
        forum_post_response.status_code = 200

        client._create_forum_post = unittest.mock.MagicMock(  # pylint: disable=protected-access
            name='_create_forum_post',
            return_value=forum_post_response
        )
        client._delete_content_metadata = unittest.mock.MagicMock(name='_delete_content_metadata')  # pylint: disable=protected-access
        with pytest.raises(ClientError) as err2:
            client.create_content_metadata(serialize_copy)

        client._delete_content_metadata.called_once()  # pylint: disable=protected-access
        assert err2.value.message == 'Moodle Client Content Metadata Creation failed to create ' \
                                     'post for course {}'.format(expected_data['courses[0][shortname]'])

    def test_update_content_metadata(self):
        """
        Test core logic of update_content_metadata to ensure
        query string we send to Moodle is formatted correctly.
        """
        expected_data = SERIALIZED_DATA.copy()
        input_data = SERIALIZED_DATA.copy()
        expected_data['courses[0][id]'] = self.moodle_course_id
        expected_data['wsfunction'] = 'core_course_update_courses'
        expected_data['courses[0][format]'] = 'singleactivity'
        input_data['courses[0][announcement]'] = 'whatever'
        input_data['courses[0][format]'] = 'singleactivity'

        client = MoodleAPIClient(self.enterprise_config)
        content_response = unittest.mock.Mock(spec=Response)
        content_response.json.return_value = {'warnings': []}
        content_response.status_code = 200
        client._post = unittest.mock.MagicMock(name='_post', return_value=content_response)  # pylint: disable=protected-access
        client._wrapped_update_content_metadata = unittest.mock.MagicMock(  # pylint: disable=protected-access
            name='_wrapped_update_content_metadata', return_value=content_response)
        client.get_course_id = unittest.mock.MagicMock(name='_get_course_id')
        client.get_course_id.return_value = self.moodle_course_id
        client.get_announcement_forum = unittest.mock.MagicMock(name='get_announcement_forum')
        client.get_announcement_forum.return_value = 2
        client.get_announcement_post = unittest.mock.MagicMock(name='get_announcement_post')
        client.get_announcement_post.return_value = 2
        client.update_content_metadata(input_data)
        client._wrapped_update_content_metadata.assert_called_once_with(expected_data)  # pylint: disable=protected-access

    def test_delete_content_metadata(self):
        """
        Test core logic for formatting a delete request to Moodle.
        """
        expected_data = {'wsfunction': 'core_course_delete_courses', 'courseids[]': self.moodle_course_id}

        client = MoodleAPIClient(self.enterprise_config)
        client._post = unittest.mock.MagicMock(name='_post', return_value=SUCCESSFUL_RESPONSE)  # pylint: disable=protected-access
        client.get_course_id = unittest.mock.MagicMock(name='_get_course_id')
        client.get_course_id.return_value = self.moodle_course_id
        client.delete_content_metadata(SERIALIZED_DATA)

        client._post.assert_called_once_with(expected_data)  # pylint: disable=protected-access

    def test_course_completion_with_no_course(self):
        """Test that we properly raise exceptions if the client receives a 404 from Moodle"""
        with responses.RequestsMock() as rsps:
            moodle_api_path = urljoin(
                self.enterprise_config.moodle_base_url,
                self.moodle_api_path,
            )
            moodle_get_courses_query = 'wstoken={}&wsfunction=core_course_get_courses_by_field&field=shortname' \
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
