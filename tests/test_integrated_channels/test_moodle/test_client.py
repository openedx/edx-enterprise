# -*- coding: utf-8 -*-
"""
Tests for clients in integrated_channels.
"""

import datetime
import unittest

import pytest
from freezegun import freeze_time

from django.utils import timezone

from integrated_channels.moodle.client import MoodleAPIClient
from test_utils import factories

NOW = datetime.datetime(2017, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
NOW_TIMESTAMP_FORMATTED = NOW.strftime('%F')


@freeze_time(NOW)
@pytest.mark.django_db
class TestMoodleApiClient(unittest.TestCase):
    """
    Test Moodle API client methods.
    """

    def setUp(self):
        super(TestMoodleApiClient, self).setUp()
        self.moodle_base_url = 'http://testing/'
        self.api_token = 'token',
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

