# -*- coding: utf-8 -*-
"""
Test for xAPI utility functions.
"""

from __future__ import absolute_import, unicode_literals

import unittest

import mock
from faker import Factory as FakerFactory
from pytest import mark

from integrated_channels.xapi.client import EnterpriseXAPIClient
from integrated_channels.xapi.utils import send_course_enrollment_statement
from test_utils import factories


@mark.django_db
class TestUtils(unittest.TestCase):
    """
    Tests for the xAPI Utility Functions.
    """

    def setUp(self):
        super(TestUtils, self).setUp()
        faker = FakerFactory.create()

        self.user = factories.UserFactory()
        # pylint: disable=no-member
        self.course_overview = mock.Mock(display_name=faker.text(max_nb_chars=25), short_description=faker.text())
        self.course_enrollment = mock.Mock(user=self.user, course=self.course_overview)

        self.x_api_lrs_config = factories.XAPILRSConfigurationFactory()
        self.x_api_client = EnterpriseXAPIClient(self.x_api_lrs_config)

    @mock.patch('integrated_channels.xapi.client.RemoteLRS', mock.MagicMock())
    def test_send_course_enrollment_statement(self):
        """
        Verify that send_course_enrollment_statement sends XAPI statement to LRS.
        """
        send_course_enrollment_statement(self.x_api_lrs_config, self.course_enrollment)

        self.x_api_client.lrs.save_statement.assert_called()  # pylint: disable=no-member
