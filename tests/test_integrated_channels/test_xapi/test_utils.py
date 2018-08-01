# -*- coding: utf-8 -*-
"""
Test for xAPI utility functions.
"""

from __future__ import absolute_import, unicode_literals

import unittest
from datetime import datetime, timedelta

import mock
from faker import Factory as FakerFactory
from pytest import mark

from integrated_channels.xapi.client import EnterpriseXAPIClient
from integrated_channels.xapi.utils import send_course_completion_statement, send_course_enrollment_statement
from test_utils import factories


@mark.django_db
class TestUtils(unittest.TestCase):
    """
    Tests for the xAPI Utility Functions.
    """

    def setUp(self):
        super(TestUtils, self).setUp()
        self.faker = FakerFactory.create()

        self.user = factories.UserFactory()
        self.user.profile = mock.Mock(country=mock.Mock(code='PK'))

        now = datetime.now()
        # pylint: disable=no-member
        self.course_overview_mock_data = dict(
            id=self.faker.text(max_nb_chars=25),  # pylint: disable=no-member
            display_name=self.faker.text(max_nb_chars=25),  # pylint: disable=no-member
            short_description=self.faker.text(),  # pylint: disable=no-member
            marketing_url=self.faker.url(),  # pylint: disable=no-member
            effort=self.faker.text(max_nb_chars=10),  # pylint: disable=no-member
            start=now,
            end=now + timedelta(weeks=3, days=4),
        )
        self.course_overview = mock.Mock(**self.course_overview_mock_data)

        self.course_enrollment = mock.Mock(user=self.user, course=self.course_overview)
        self.course_grade = mock.Mock(percent=0.80, passed=True)

        self.x_api_lrs_config = factories.XAPILRSConfigurationFactory()
        self.x_api_client = EnterpriseXAPIClient(self.x_api_lrs_config)

    @mock.patch('integrated_channels.xapi.client.RemoteLRS', mock.MagicMock())
    def test_send_course_enrollment_statement(self):
        """
        Verify that send_course_enrollment_statement sends xAPI statement to LRS.
        """
        send_course_enrollment_statement(self.x_api_lrs_config, self.course_enrollment)

        self.x_api_client.lrs.save_statement.assert_called()  # pylint: disable=no-member

    @mock.patch('integrated_channels.xapi.client.RemoteLRS', mock.MagicMock())
    def test_send_course_completion_statement(self):
        """
        Verify that send_course_completion_statement sends xAPI statement to LRS.
        """
        send_course_completion_statement(
            self.x_api_lrs_config,
            self.user,
            self.course_overview,
            self.course_grade,
        )

        self.x_api_client.lrs.save_statement.assert_called()  # pylint: disable=no-member
