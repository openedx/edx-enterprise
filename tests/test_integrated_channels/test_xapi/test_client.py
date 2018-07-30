# -*- coding: utf-8 -*-
"""
Test for xAPI client.
"""

from __future__ import absolute_import, unicode_literals

import unittest

import mock
from pytest import mark, raises

from integrated_channels.exceptions import ClientError
from integrated_channels.xapi.client import EnterpriseXAPIClient
from test_utils import factories


@mark.django_db
class TestXAPILRSConfiguration(unittest.TestCase):
    """
    Tests for the ``XAPILRSConfiguration`` model.
    """

    def setUp(self):
        super(TestXAPILRSConfiguration, self).setUp()
        self.x_api_lrs_config = factories.XAPILRSConfigurationFactory()
        self.x_api_client = EnterpriseXAPIClient(self.x_api_lrs_config)

    @mock.patch('integrated_channels.xapi.client.RemoteLRS', mock.MagicMock())
    def test_save_statement(self):
        """
        Verify that save_statement sends xAPI statement to LRS.
        """
        # verify that request completes without an error.
        self.x_api_client.save_statement({})
        self.x_api_client.lrs.save_statement.assert_called_once_with({})

    @mock.patch('integrated_channels.xapi.client.RemoteLRS', mock.MagicMock())
    def test_save_statement_raises_client_error(self):
        """
        Verify that save_statement raises ClientError if it could not complete request successfully.
        """
        self.x_api_client.lrs.save_statement = mock.Mock(return_value=None)

        with raises(ClientError):
            self.x_api_client.save_statement({})
