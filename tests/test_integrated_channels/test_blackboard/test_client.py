# -*- coding: utf-8 -*-
"""
Tests for clients in integrated_channels.blackboard.
"""

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

    def test_client_has_valid_configs(self):
        api_client = BlackboardAPIClient(self.enterprise_config)
        assert api_client.config is not None
        assert api_client.config.name == CHANNEL_NAME
        assert api_client.config.verbose_name == VERBOSE_NAME
        assert api_client.enterprise_configuration == self.enterprise_config

    def test_course_completion_with_no_course(self):
        """Test that we properly raise exceptions if the client receives a 404 from Blackboard"""
        client = BlackboardAPIClient(self.enterprise_config)
        client._get_oauth_access_token = unittest.mock.MagicMock(  # pylint: disable=protected-access
            name="_get_oauth_access_token",
            return_value=(self.token, 10000)
        )

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

    def test_client_behavior_on_successful_learner_data_transmission(self):  # pylint: disable=protected-access
        """
        Test that given successful requests for Blackboard learner data,
        the client makes the appropriate _patch call to update a user's grade
        """
        client = BlackboardAPIClient(self.enterprise_config)
        # Mock the auth process
        client._get_oauth_access_token = unittest.mock.MagicMock(  # pylint: disable=protected-access
            name="_get_oauth_access_token",
            return_value=(self.token, 10000)
        )

        # Mock the course ID request
        client._get_courses_by_internal_id = unittest.mock.MagicMock(  # pylint: disable=protected-access
            name="_get_courses_by_internal_id",
            return_value=[{
                'externalId': self.course_id,
                'id': self.blackboard_course_id
            }]
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
