# -*- coding: utf-8 -*-
"""
Tests for the `sap_success_factors` package.
"""

from __future__ import absolute_import, unicode_literals, with_statement

import unittest

import ddt
import mock
from integrated_channels.sap_success_factors.utils import (
    current_time_is_in_interval,
    get_course_track_selection_url,
    parse_datetime_to_epoch,
    transform_language_code,
)
from pytest import raises

from enterprise.api_client.lms import parse_lms_api_datetime


@ddt.ddt
class TestSapSuccessFactorsUtils(unittest.TestCase):
    """
    Test the individual functions used by the SAPSuccessFactors course transformation.
    """

    @ddt.data(
        ('cy', 'Welsh'),
        ('en-us', 'English'),
        ('zh-hk', 'Chinese Hong Kong'),
        ('ru-faaaaaake', 'Russian'),
        ('not-real', 'English')
    )
    @ddt.unpack
    def test_transform_language_code_valid(self, code, expected):
        assert transform_language_code(code) == expected

    def test_unparsable_language_code(self):
        with raises(ValueError) as exc_info:
            transform_language_code('this-is-incomprehensible')
        assert str(exc_info.value) == (
            'Language codes may only have up to two components. Could not parse: this-is-incomprehensible'
        )

    @ddt.data(
        ('2011-01-01T00:00:00Z', '2011-01-01T00:00:00Z', False),
        ('2015-01-01T00:00:00Z', '2017-01-01T00:00:00Z', True),
        ('2018-01-01T00:00:00Z', '2020-01-01T00:00:00Z', False),
    )
    @ddt.unpack
    @mock.patch('integrated_channels.sap_success_factors.utils.timezone')
    def test_current_time_in_interval(self, start, end, expected, fake_timezone):
        fake_timezone.now.return_value = parse_lms_api_datetime('2016-01-01T00:00:00Z')
        assert current_time_is_in_interval(start, end) is expected

    @ddt.data(
        ('1970-01-01T00:00:00Z', 0),
        ('2017-04-04T18:45:51Z', 1491331551000),
    )
    @ddt.unpack
    def test_parse_datetime_to_epoch(self, iso8601, epoch):
        assert parse_datetime_to_epoch(iso8601) == epoch

    @ddt.data(
        (
            'https',
            'example.com',
            'course-v1:edX+DemoX+Demo_Course',
            'some_idp',
            'https://example.com/course_modes/choose/course-v1:edX+DemoX+Demo_Course/?tpa_hint=some_idp',
        ),
        (
            'ftp',
            'otherdomain.com',
            'course-v1:Starfleet+Phaser101+Spring_2017',
            None,
            'ftp://otherdomain.com/course_modes/choose/course-v1:Starfleet+Phaser101+Spring_2017/',
        )
    )
    @ddt.unpack
    @mock.patch('integrated_channels.sap_success_factors.utils.reverse')
    def test_get_course_track_selection_url(
            self,
            scheme,
            domain,
            course_id,
            identity_provider,
            expected_url,
            reverse_mock
    ):
        reverse_mock.return_value = '/course_modes/choose/{}/'.format(course_id)
        with mock.patch('integrated_channels.sap_success_factors.utils.COURSE_URL_SCHEME', scheme):
            enterprise_customer = mock.MagicMock(
                site=mock.MagicMock(domain=domain),
                identity_provider=identity_provider
            )
            assert get_course_track_selection_url(enterprise_customer, course_id) == expected_url
            reverse_mock.assert_called_once_with('course_modes_choose', args=[course_id])
