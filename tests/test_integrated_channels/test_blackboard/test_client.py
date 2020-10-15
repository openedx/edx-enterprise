# -*- coding: utf-8 -*-
"""
Tests for clients in integrated_channels.blackboard.
"""

import json
import random
import unittest

import pytest
from requests.models import Response

from integrated_channels.blackboard.apps import CHANNEL_NAME, VERBOSE_NAME
from integrated_channels.blackboard.client import BlackboardAPIClient
from integrated_channels.exceptions import ClientError
from test_utils.factories import BlackboardEnterpriseCustomerConfigurationFactory

COURSE_NOT_FOUND_RESPONSE = unittest.mock.Mock(spec=Response)
COURSE_NOT_FOUND_RESPONSE.text = 'NOT FOUND'
COURSE_NOT_FOUND_RESPONSE.json.return_value = {}
COURSE_NOT_FOUND_RESPONSE.status_code = 404

SUCCESSFUL_RESPONSE = unittest.mock.Mock(spec=Response)
SUCCESSFUL_RESPONSE.status_code = 200


@pytest.mark.django_db
class TestBlackboardApiClient(unittest.TestCase):
    """
    Test Blackboard API client methods.
    """

    def setUp(self):
        super(TestBlackboardApiClient, self).setUp()
        self.token = "token"
        self.enterprise_config = BlackboardEnterpriseCustomerConfigurationFactory(
            client_id="id",
            client_secret="secret",
            blackboard_base_url="https://base.url",
            refresh_token=self.token,
        )
        self.user_email = 'testemail@example.com'
        self.course_id = 'course-edx+{}'.format(str(random.randint(100, 999)))
        self.blackboard_course_id = random.randint(100, 999)
        self.blackboard_user_id = random.randint(100, 999)
        self.blackboard_grade_column_id = random.randint(100, 999)
        self.grade = round(random.uniform(0, 1), 2)
        self.learner_data_payload = '{{"courseID": "{}", "grade": {}}}'.format(self.course_id, self.grade)

        SUCCESSFUL_RESPONSE.json.return_value = {
            'score': self.grade * 100
        }

    def _create_new_mock_client(self):
        """Test client instance with oauth token filled in"""
        client = BlackboardAPIClient(self.enterprise_config)
        client._get_oauth_access_token = unittest.mock.MagicMock(  # pylint: disable=protected-access
            name="_get_oauth_access_token",
            return_value=(self.token, 10000)
        )
        return client

    def test_client_has_valid_configs(self):
        api_client = BlackboardAPIClient(self.enterprise_config)
        assert api_client.config is not None
        assert api_client.config.name == CHANNEL_NAME
        assert api_client.config.verbose_name == VERBOSE_NAME
        assert api_client.enterprise_configuration == self.enterprise_config

    def test_course_completion_with_no_course(self):
        """Test that we properly raise exceptions if the client receives a 404 from Blackboard"""
        client = self._create_new_mock_client()

        # Create the session so that we can mock the requests made in the course completion transmission flow
        client._create_session()  # pylint: disable=protected-access
        client.session.get = unittest.mock.MagicMock(
            name="_get",
            return_value=COURSE_NOT_FOUND_RESPONSE
        )
        with pytest.raises(ClientError) as client_error:
            client.create_course_completion(self.user_email, self.learner_data_payload)

        assert client_error.value.message == COURSE_NOT_FOUND_RESPONSE.text
        assert client_error.value.status_code == COURSE_NOT_FOUND_RESPONSE.status_code == 404

    def test_create_content_metadata_success(self):
        client = self._create_new_mock_client()
        course_id = "a-course-id"
        serialized_data = json.dumps({
            "externalId": course_id
        }).encode('utf-8')
        success_response = unittest.mock.Mock(spec=Response)
        success_response.status_code = 200
        success_response.text = "hooray"
        success_response.json.return_value = {}

        client._create_session()  # pylint: disable=protected-access
        client._post = unittest.mock.MagicMock(  # pylint: disable=protected-access
            name="_post",
            return_value=success_response
        )

        status_code, status_text = client.create_content_metadata(serialized_data)

        assert status_code == 200
        assert status_text == "hooray"

        expected_url = client.generate_course_create_url()
        expected_channel_data = {
            "externalId": course_id,
            "courseId": client.generate_blackboard_course_id(course_id),
        }
        expected_data = expected_channel_data
        client._post.assert_called_with(expected_url, expected_data)  # pylint: disable=protected-access

    def test_update_content_metadata_success(self):  # pylint: disable=protected-access
        client = self._create_new_mock_client()
        serialized_data = json.dumps({
            "externalId": "a-course-id"
        }).encode('utf-8')
        success_response = unittest.mock.Mock(spec=Response)
        success_response.status_code = 200
        success_response.text = "hooray"
        success_response.json.return_value = {}

        client._create_session()  # pylint: disable=protected-access
        client._patch = unittest.mock.MagicMock(  # pylint: disable=protected-access
            name="_patch",
            return_value=success_response
        )
        client._resolve_blackboard_course_id = unittest.mock.MagicMock(  # pylint: disable=protected-access
            name="_resolve_blackboard_course_id",
            return_value="a-course-id"
        )

        status_code, status_text = client.update_content_metadata(serialized_data)

        assert status_code == 200
        assert status_text == "hooray"

        expected_url = client.generate_course_update_url("a-course-id")
        client._patch.assert_called_with(expected_url, json.loads(serialized_data.decode("utf-8")))  # pylint: disable=protected-access
        assert client._resolve_blackboard_course_id.called  # pylint: disable=protected-access

    def test_delete_content_metadata(self):
        client = self._create_new_mock_client()
        serialized_data = json.dumps({
            "externalId": "a-course-id"
        }).encode('utf-8')
        success_response = unittest.mock.Mock(spec=Response)
        success_response.status_code = 202
        success_response.text = ""
        success_response.json.return_value = {}

        client._create_session()  # pylint: disable=protected-access
        client._delete = unittest.mock.MagicMock(  # pylint: disable=protected-access
            name="_delete",
            return_value=success_response
        )
        client._resolve_blackboard_course_id = unittest.mock.MagicMock(  # pylint: disable=protected-access
            name="_resolve_blackboard_course_id",
            return_value="a-course-id"
        )

        status_code, status_text = client.delete_content_metadata(serialized_data)

        assert status_code == 202
        assert status_text == ""

        expected_url = client.generate_course_update_url("a-course-id")
        client._delete.assert_called_with(expected_url)  # pylint: disable=protected-access
        assert client._resolve_blackboard_course_id.called  # pylint: disable=protected-access

    def test_client_behavior_on_successful_learner_data_transmission(self):  # pylint: disable=protected-access
        """
        Test that given successful requests for Blackboard learner data,
        the client makes the appropriate _patch call to update a user's grade
        """
        client = self._create_new_mock_client()

        # Mock the course ID request
        client._resolve_blackboard_course_id = unittest.mock.MagicMock(  # pylint: disable=protected-access
            name="_resolve_blackboard_course_id",
            return_value=self.course_id,
        )

        # Mock the enrollments request
        client._get_bb_user_id_from_enrollments = unittest.mock.MagicMock(  # pylint: disable=protected-access
            name="_get_bb_user_id_from_enrollments",
            return_value=self.blackboard_user_id
        )

        # Mock the gradebook/column request
        client._get_or_create_integrated_grade_column = unittest.mock.MagicMock(  # pylint: disable=protected-access
            name="_get_or_create_integrated_grade_column",
            return_value=self.blackboard_grade_column_id
        )

        # Create the session so that we can mock the requests made in the course completion transmission flow
        client._create_session()  # pylint: disable=protected-access
        client.session.patch = unittest.mock.MagicMock(
            name='_patch',
            return_value=SUCCESSFUL_RESPONSE
        )

        expected_success_body = 'Successfully posted grade of {grade} to ' \
                                'course:{course_id} for user:{user_email}.'.format(
                                    grade=self.grade * 100,
                                    course_id=self.course_id,
                                    user_email=self.user_email,
                                )

        assert client.create_course_completion(
            self.user_email,
            self.learner_data_payload
        ) == (SUCCESSFUL_RESPONSE.status_code, expected_success_body)
