# -*- coding: utf-8 -*-
"""
Tests for clients in integrated_channels.
"""

import unittest
from urllib.parse import quote

import pytest

from integrated_channels.moodle.client import MoodleAPIClient
from test_utils import factories

SERIALIZED_DATA = {
    'courses[0][summary]': 'edX Demonstration Course',
    'courses[0][shortname]': 'edX+DemoX',
    'courses[0][startdate]': '2030-01-01T00:00:00Z',
    'courses[0][enddate]': '2030-03-01T00:00:00Z',
}

MOODLE_COURSE_ID = 100


@pytest.mark.django_db
class TestMoodleApiClient(unittest.TestCase):
    """
    Test Moodle API client methods.
    """

    def setUp(self):
        super(TestMoodleApiClient, self).setUp()
        self.moodle_base_url = 'http://testing/'
        self.api_token = 'token'
        self.password = 'pass'
        self.user = 'user'
        self.enterprise_config = factories.MoodleEnterpriseCustomerConfigurationFactory(
            moodle_base_url=self.moodle_base_url,
            wsusername=self.user,
            wspassword=self.password,
            api_token=self.api_token,
        )

    def test_moodle_config_is_set(self):
        """
        Test global_moodle_config is setup.
        """
        moodle_api_client = MoodleAPIClient(self.enterprise_config)
        assert moodle_api_client.config is not None

    def test_update_content_metadata(self):
        """
        Test core logic of update_content_metadata to ensure
        query string we send to Moodle is formatted correctly.
        """
        expected_data = SERIALIZED_DATA.copy()
        expected_data['courses[0][id]'] = MOODLE_COURSE_ID
        expected_data['wsfunction'] = 'core_course_update_courses'

        client = MoodleAPIClient(self.enterprise_config)
        client._post = unittest.mock.MagicMock(name='_post')  # pylint: disable=protected-access
        client.get_course_id = unittest.mock.MagicMock(name='_get_course_id')
        client.get_course_id.return_value = MOODLE_COURSE_ID
        client.update_content_metadata(SERIALIZED_DATA)
        client._post.assert_called_once_with(self.moodle_base_url, expected_data)  # pylint: disable=protected-access

    def test_delete_content_metadata(self):
        """
        Test core logic for formatting a delete request to Moodle.
        """
        expected_data = {'wsfunction': 'core_course_delete_courses'}
        expected_url = self.moodle_base_url + quote('?courseids[]={0}'.format(MOODLE_COURSE_ID), safe='?=')
        client = MoodleAPIClient(self.enterprise_config)
        client._post = unittest.mock.MagicMock(name='_post')  # pylint: disable=protected-access
        client.get_course_id = unittest.mock.MagicMock(name='_get_course_id')
        client.get_course_id.return_value = MOODLE_COURSE_ID
        client.delete_content_metadata(SERIALIZED_DATA)

        client._post.assert_called_once_with(expected_url, expected_data)  # pylint: disable=protected-access
