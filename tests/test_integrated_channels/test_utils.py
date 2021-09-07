# -*- coding: utf-8 -*-
"""
Tests for the utilities used by integration channels.
"""

import unittest
from collections import namedtuple
from datetime import timedelta

import ddt
import mock
from pytest import raises

from enterprise.utils import parse_lms_api_datetime
from integrated_channels import utils

ent_enrollment = namedtuple('enterprise_enrollment', ['is_audit_enrollment'])


@ddt.ddt
class TestIntegratedChannelsUtils(unittest.TestCase):
    """
    Test utility functions used by integration channels.
    """

    @ddt.data(
        ('course-v1:edX+808404707+2T2021/', 'Y291cnNlLXYxOmVkWCs4MDg0MDQ3MDcrMlQyMDIxLw=='),
        ('edx+123', 'ZWR4KzEyMw=='),
        ('UTAustinX/UT.7.01x/3T2014', 'VVRBdXN0aW5YL1VULjcuMDF4LzNUMjAxNA=='),
        ('WellesleyX/ENG_112x/2014_SOND', 'V2VsbGVzbGV5WC9FTkdfMTEyeC8yMDE0X1NPTkQ=')

    )
    @ddt.unpack
    def test_encode_course_key_for_lms(self, edx_key, lms_key):
        assert utils.encode_course_key_into_base64(edx_key) == lms_key
        assert utils.decode_course_key_from_base64(lms_key) == edx_key

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

    @ddt.data(
        (
            timedelta(days=18, hours=7, minutes=19, seconds=26),
            '{D:02}d {H:02}h {M:02}m {S:02}s',
            'timedelta',
            '18d 07h 19m 26s',
        ),
        (
            18 * 24 * 60 * 60 + 7 * 60 * 60 + 19 * 60 + 26,  # seconds in 18d 7h 19m 26s
            '{D:02}d {H:02}h {M:02}m {S:02}s',
            'seconds',
            '18d 07h 19m 26s',
        ),
        (
            18 * 24 * 60 + 7 * 60 + 19,  # minutes in 18d 7h 19m
            '{D:02}d {H:02}h {M:02}m',
            'minutes',
            '18d 07h 19m',
        ),
        (
            18 * 24 + 7,  # hours in 18d 7h
            '{D:02}d {H:02}h',
            'hours',
            '18d 07h',
        ),
        (
            18,  # 18 days
            '{D:02}d',
            'days',
            '18d',
        ),
        (
            7,  # 7 weeks
            '{D:02}d',
            'weeks',
            '49d',
        ),
        (
            timedelta(days=18),
            '{W} weeks {D} days.',
            'timedelta',
            '2 weeks 4 days.',
        ),
    )
    @ddt.unpack
    def test_strfdelta(self, duration, fmt, input_type, expected):
        assert utils.strfdelta(duration, fmt, input_type) == expected

    def test_strfdelta_value_error(self):
        with raises(ValueError):
            utils.strfdelta(timedelta(days=1), input_type='invalid_type')

    @mock.patch('integrated_channels.utils.get_course_run_for_enrollment')
    def test_is_course_completed_audit_complete(self, mock_get_course_run_for_enrollment):
        course_run_verify_expired = {'seats': [{
            'type': 'verified',
            'upgrade_deadline': '2000-10-13T13:10:04Z'
        }]}
        mock_get_course_run_for_enrollment.return_value = course_run_verify_expired
        enterprise_enrollment = ent_enrollment(is_audit_enrollment=True)
        assert utils.is_course_completed(enterprise_enrollment, None, True, 0)

    @mock.patch('integrated_channels.utils.get_course_run_for_enrollment')
    def test_is_course_completed_audit_incomplete(self, mock_get_course_run_for_enrollment):
        course_run_verify_non_expired = {'seats': [{
            'type': 'verified',
            'upgrade_deadline': '9000-10-13T13:11:04Z'
        }]}
        mock_get_course_run_for_enrollment.return_value = course_run_verify_non_expired
        enterprise_enrollment = ent_enrollment(is_audit_enrollment=True)
        assert not utils.is_course_completed(enterprise_enrollment, None, True, 0)

    @mock.patch('integrated_channels.utils.get_course_run_for_enrollment')
    def test_is_course_completed_nonaudit_complete(self, mock_get_course_run_for_enrollment):
        course_run_verify_expired = {'seats': [{
            'type': 'verified',
            'upgrade_deadline': '2000-10-13T13:01:04Z'
        }]}
        mock_get_course_run_for_enrollment.return_value = course_run_verify_expired
        enterprise_enrollment = ent_enrollment(is_audit_enrollment=False)
        assert utils.is_course_completed(enterprise_enrollment, '2000-10-13T13:11:04Z', True, 0)

    @mock.patch('integrated_channels.utils.get_course_run_for_enrollment')
    def test_is_course_completed_nonaudit_incomplete(self, mock_get_course_run_for_enrollment):
        course_run_verify_expired = {'seats': [{
            'type': 'verified',
            'upgrade_deadline': '2000-10-13T13:11:04Z'
        }]}
        mock_get_course_run_for_enrollment.return_value = course_run_verify_expired
        enterprise_enrollment = ent_enrollment(is_audit_enrollment=False)
        assert not utils.is_course_completed(enterprise_enrollment, None, False, 0)
