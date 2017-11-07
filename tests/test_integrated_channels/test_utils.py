# -*- coding: utf-8 -*-
"""
Tests for the utilities used by integration channels.
"""

from __future__ import absolute_import, unicode_literals, with_statement

import unittest

import ddt
import mock
from integrated_channels import utils

from enterprise.api_client.lms import parse_lms_api_datetime


@ddt.ddt
class TestIntegratedChannelsUtils(unittest.TestCase):
    """
    Test utility functions used by integration channels.
    """

    @ddt.data(
        ('2011-01-01T00:00:00Z', '2011-01-01T00:00:00Z', False),
        ('2015-01-01T00:00:00Z', '2017-01-01T00:00:00Z', True),
        ('2018-01-01T00:00:00Z', '2020-01-01T00:00:00Z', False),
        ('2018-01-01T00:00:00', '2020-01-01T00:00:00', False),
    )
    @ddt.unpack
    @mock.patch('integrated_channels.utils.timezone')
    def test_current_time_in_interval(self, start, end, expected, fake_timezone):
        fake_timezone.now.return_value = parse_lms_api_datetime('2016-01-01T00:00:00Z')
        assert utils.current_time_is_in_interval(start, end) is expected

    @ddt.data(
        ('1970-01-01T00:00:00Z', 0),
        ('2017-04-04T18:45:51Z', 1491331551000),
    )
    @ddt.unpack
    def test_parse_datetime_to_epoch(self, iso8601, epoch):
        assert utils.parse_datetime_to_epoch_millis(iso8601) == epoch
