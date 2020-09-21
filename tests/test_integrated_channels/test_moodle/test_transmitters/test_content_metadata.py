# -*- coding: utf-8 -*-
"""
Tests for the Moodle content metadata transmitter.
"""

import unittest

from pytest import mark

from integrated_channels.moodle.transmitters.content_metadata import MoodleContentMetadataTransmitter
from test_utils import factories


@mark.django_db
class TestMoodleContentMetadataTransmitter(unittest.TestCase):
    """
    Tests for the class ``MoodleContentMetadataTransmitter``.
    """

    def setUp(self):
        super(TestMoodleContentMetadataTransmitter, self).setUp()
        self.moodle_base_url = 'http://testing/'
        self.api_token = 'token'
        self.password = 'pass'
        self.user = 'user'
        self.enterprise_config = factories.MoodleEnterpriseCustomerConfigurationFactory(
            moodle_base_url=self.moodle_base_url,
            username=self.user,
            password=self.password,
            token=self.api_token,
        )

    def test_prepare_items_for_transmission(self):
        channel_metadata_items = [
            {
                'title': 'edX Demonstration Course',
                'key': 'edX+DemoX',
                'content_type': 'course',
                'start': '2030-01-01T00:00:00Z',
                'end': '2030-03-01T00:00:00Z'
            },
            {
                'title': 'edX Demonstration Course',
                'key': 'edX+DemoX2',
                'content_type': 'course',
                'start': '2030-01-01T00:00:00Z',
                'end': '2030-03-01T00:00:00Z'
            }
        ]

        expected_prepared_items = {
            'courses[0][title]': 'edX Demonstration Course',
            'courses[0][key]': 'edX+DemoX',
            'courses[0][content_type]': 'course',
            'courses[0][start]': '2030-01-01T00:00:00Z',
            'courses[0][end]': '2030-03-01T00:00:00Z',
            'courses[1][title]': 'edX Demonstration Course',
            'courses[1][key]': 'edX+DemoX2',
            'courses[1][content_type]': 'course',
            'courses[1][start]': '2030-01-01T00:00:00Z',
            'courses[1][end]': '2030-03-01T00:00:00Z'
        }

        transmitter = MoodleContentMetadataTransmitter(self.enterprise_config)
        assert transmitter._prepare_items_for_transmission(channel_metadata_items) == expected_prepared_items  # pylint: disable=protected-access
