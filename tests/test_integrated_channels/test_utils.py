"""
Tests for the utilities used by integration channels.
"""

import json
import unittest
from collections import namedtuple
from datetime import timedelta, timezone
from unittest import mock
from unittest.mock import MagicMock, PropertyMock

import ddt
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
        ('WellesleyX/ENG_112x/2014_SOND', 'V2VsbGVzbGV5WC9FTkdfMTEyeC8yMDE0X1NPTkQ='),
        ({'one': 'foo', 2: 'bar'}, 'eyJvbmUiOiAiZm9vIiwgIjIiOiAiYmFyIn0='),
        (['one', 2, 'three', 4], 'WyJvbmUiLCAyLCAidGhyZWUiLCA0XQ==')
    )
    @ddt.unpack
    def test_encode_data_for_logging(self, input_data, output_base64_str):
        assert utils.encode_data_for_logging(input_data) == output_base64_str

    @ddt.data(
        ('2011-01-01T00:00:00Z', '2011-01-01T00:00:00Z', False),
        ('2015-01-01T00:00:00Z', '2017-01-01T00:00:00Z', True),
        ('2018-01-01T00:00:00Z', '2020-01-01T00:00:00Z', False),
        ('2018-01-01T00:00:00', '2020-01-01T00:00:00', False),
    )
    @ddt.unpack
    @mock.patch('integrated_channels.utils.datetime')
    def test_current_time_in_interval(self, start, end, expected, fake_datetime):
        fake_datetime.now.return_value = parse_lms_api_datetime('2016-01-01T00:00:00Z')
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
        assert not utils.is_course_completed(enterprise_enrollment, None, True, 0)
        assert utils.is_course_completed(enterprise_enrollment, True, 0, None)

    @mock.patch('integrated_channels.utils.get_course_run_for_enrollment')
    def test_is_course_completed_audit_incomplete(self, mock_get_course_run_for_enrollment):
        course_run_verify_non_expired = {'seats': [{
            'type': 'verified',
            'upgrade_deadline': '9000-10-13T13:11:04Z'
        }]}
        mock_get_course_run_for_enrollment.return_value = course_run_verify_non_expired
        enterprise_enrollment = ent_enrollment(is_audit_enrollment=True)
        assert not utils.is_course_completed(enterprise_enrollment, False, 1, None)

    @mock.patch('integrated_channels.utils.get_course_run_for_enrollment')
    def test_is_course_completed_nonaudit_complete(self, mock_get_course_run_for_enrollment):
        course_run_verify_expired = {'seats': [{
            'type': 'verified',
            'upgrade_deadline': '2000-10-13T13:01:04Z'
        }]}
        mock_get_course_run_for_enrollment.return_value = course_run_verify_expired
        enterprise_enrollment = ent_enrollment(is_audit_enrollment=False)
        assert utils.is_course_completed(enterprise_enrollment, True, 0, '2000-10-13T13:11:04Z')

    @mock.patch('integrated_channels.utils.get_course_run_for_enrollment')
    def test_is_course_completed_nonaudit_incomplete(self, mock_get_course_run_for_enrollment):
        course_run_verify_expired = {'seats': [{
            'type': 'verified',
            'upgrade_deadline': '2000-10-13T13:11:04Z'
        }]}
        mock_get_course_run_for_enrollment.return_value = course_run_verify_expired
        enterprise_enrollment = ent_enrollment(is_audit_enrollment=False)
        assert not utils.is_course_completed(enterprise_enrollment, True, 0, None)
        assert not utils.is_course_completed(enterprise_enrollment, False, 0, '2000-10-13T13:11:04Z')

    @ddt.data((True, True,), (False, False,))
    @ddt.unpack
    def test_is_already_transmitted_with_grade_considered(
        self,
        grade_should_match_audit,
        expected_is_already_transmitted,
    ):
        """
        When detect_grade_updated is True, grade is also matched against passed grade,
        when comparing audit records
        """
        transmission = MagicMock()
        transmission.objects.filter = MagicMock()
        mock_audit_record = MagicMock()
        mock_audit_record.latest = MagicMock()
        matching_grade = 'A+'

        mock_audit_record_from_audit_logs = MagicMock()
        grade_match = PropertyMock(return_value=matching_grade)
        grade_non_matched = PropertyMock(return_value='B+')
        if grade_should_match_audit:
            type(mock_audit_record_from_audit_logs).grade = grade_match
        else:
            type(mock_audit_record_from_audit_logs).grade = grade_non_matched

        mock_audit_record.latest.return_value = mock_audit_record_from_audit_logs

        transmission.objects.filter.return_value = mock_audit_record

        enterprise_enrollment_id = 123
        enterprise_configuration_id = 456

        # note: detect_grade_updated=True by default
        assert utils.is_already_transmitted(
            transmission,
            enterprise_enrollment_id,
            enterprise_configuration_id,
            matching_grade,
            subsection_id=None,
        ) is expected_is_already_transmitted

    @ddt.data((True,), (False,))
    @ddt.unpack
    def test_is_already_transmitted_grade_not_considered(
        self,
        grade_should_match_audit,
    ):
        """
        When detect_grade_updated is False, the grade difference between database record and passed grade
        should not matter
        """
        transmission = MagicMock()
        transmission.objects.filter = MagicMock()
        mock_audit_record = MagicMock()
        mock_audit_record.latest = MagicMock()
        matching_grade = 'A+'

        mock_audit_record_from_audit_logs = MagicMock()
        grade_match = PropertyMock(return_value=matching_grade)
        grade_non_matched = PropertyMock(return_value='B+')
        if grade_should_match_audit:
            type(mock_audit_record_from_audit_logs).grade = grade_match
        else:
            type(mock_audit_record_from_audit_logs).grade = grade_non_matched

        mock_audit_record.latest.return_value = mock_audit_record_from_audit_logs

        transmission.objects.filter.return_value = mock_audit_record

        enterprise_enrollment_id = 1234
        enterprise_configuration_id = 5678

        assert utils.is_already_transmitted(
            transmission,
            enterprise_enrollment_id,
            enterprise_configuration_id,
            matching_grade,
            subsection_id=None,
            detect_grade_updated=False,
        ) is True

    def test_generate_formatted_log(self):
        log_str = utils.generate_formatted_log(1, 2, 3, 4, 5, 6)
        assert log_str == 'integrated_channel=1, '\
            'integrated_channel_enterprise_customer_uuid=2, '\
            'integrated_channel_lms_user=3, '\
            'integrated_channel_course_key=4, '\
            'integrated_channel_plugin_configuration_id=6, 5'

    def test_generate_formatted_log_old(self):
        log_str = utils.generate_formatted_log(1, 2, 3, 4, 5)
        assert log_str == 'integrated_channel=1, '\
            'integrated_channel_enterprise_customer_uuid=2, '\
            'integrated_channel_lms_user=3, '\
            'integrated_channel_course_key=4, '\
            'integrated_channel_plugin_configuration_id=None, 5'

    def test_generate_formatted_log_kwargs(self):
        log_str = utils.generate_formatted_log(channel_name="GENERIC")
        assert log_str == 'integrated_channel=GENERIC, '\
            'integrated_channel_enterprise_customer_uuid=None, '\
            'integrated_channel_lms_user=None, '\
            'integrated_channel_course_key=None, '\
            'integrated_channel_plugin_configuration_id=None, None'

    def test_is_url_valid(self):
        assert utils.is_valid_url('https://test.com/a-really-really-really-really-long-url/')
        assert utils.is_valid_url('http://test.com/')
        assert utils.is_valid_url('http://file.localdomain.tld')

        assert utils.is_valid_url('badurl.com') is False
        assert utils.is_valid_url('https://') is False

    @ddt.data(
        (
            {
                'start': '2018-02-05T05:00:00Z',
                'min_effort': 2,
                'max_effort': 4,
                'weeks_to_complete': 10
            },
            30,
        ),
        (
            {
                'start': '2018-02-05T05:00:00Z',
                'min_effort': 1,
                'max_effort': 8,
                'weeks_to_complete': 3
            },
            14,
        ),
        (
            {
                'start': '2018-02-05T05:00:00Z',
                'min_effort': 1,
                'max_effort': 8,
            },
            0,
        ),
    )
    @ddt.unpack
    def test_get_courserun_duration_in_hours(self, course_run, expected_duration_days):
        assert utils.get_courserun_duration_in_hours(course_run) == expected_duration_days

    def test_truncate_item_dicts(self):
        in_a = {'one': 1, 'two': 2, 'three': 3}
        in_b = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5}
        in_c = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7}

        # pick a max > combined input size
        out_a, out_b, out_c = utils.truncate_item_dicts(in_a, in_b, in_c, 100)

        assert len(out_a) == 3
        assert len(out_b) == 5
        assert len(out_c) == 7

        # only room for part of input A
        out_a, out_b, out_c = utils.truncate_item_dicts(in_a, in_b, in_c, 1)

        assert len(out_a) == 1
        assert len(out_b) == 0
        assert len(out_c) == 0

        # all of input A, part of input B
        out_a, out_b, out_c = utils.truncate_item_dicts(in_a, in_b, in_c, 4)

        assert len(out_a) == 3
        assert len(out_b) == 1
        assert len(out_c) == 0

        # all of input A and B, part of input C
        out_a, out_b, out_c = utils.truncate_item_dicts(in_a, in_b, in_c, 10)

        assert len(out_a) == 3
        assert len(out_b) == 5
        assert len(out_c) == 2

        in_a = {}
        in_b = {}
        in_c = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7}

        # all of input A and B (empty), all of input C
        out_a, out_b, out_c = utils.truncate_item_dicts(in_a, in_b, in_c, 10)

        assert len(out_a) == 0
        assert len(out_b) == 0
        assert len(out_c) == 7

        in_a = {'one': 1}
        in_b = {}
        in_c = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7}

        # all of input A and B (empty), all of input C
        out_a, out_b, out_c = utils.truncate_item_dicts(in_a, in_b, in_c, 10)

        assert len(out_a) == 1
        assert len(out_b) == 0
        assert len(out_c) == 7

    @mock.patch("integrated_channels.utils.integrated_channel_request_log_model")
    def test_stringify_and_store_api_record(
        self, mock_integrated_channel_request_log_model
    ):
        data = {"key": "value"}
        mock_integrated_channel_request_log_model.return_value = MagicMock()

        # Test with dict input
        stringified_data = utils.stringify_and_store_api_record(
            "Customer", 123, "/endpoint", data, 1.23, 200, "response", 'integrated_channel_name'
        )
        assert stringified_data == json.dumps(data)

        # Test with int input
        stringified_int = utils.stringify_and_store_api_record(
            "Customer", 123, "/endpoint", 123, 1.23, 200, "response", 'integrated_channel_name'
        )
        assert stringified_int == "123"

        # Test with tuple input
        data_tuple = (1, 2, "hello")
        stringified_tuple = utils.stringify_and_store_api_record(
            "Customer", 123, "/endpoint", data_tuple, 1.23, 200, "response", 'integrated_channel_name'
        )
        assert stringified_tuple == json.dumps(data_tuple)

        # Test with list input
        data_list = [1, 2, "world"]
        stringified_list = utils.stringify_and_store_api_record(
            "Customer", 123, "/endpoint", data_list, 1.23, 200, "response", 'integrated_channel_name'
        )
        assert stringified_list == json.dumps(data_list)
