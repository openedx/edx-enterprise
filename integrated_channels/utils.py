# -*- coding: utf-8 -*-
"""
Utilities common to different integrated channels.
"""

from __future__ import absolute_import, unicode_literals

import datetime

from django.utils import timezone

from enterprise.api_client.lms import parse_lms_api_datetime

UNIX_EPOCH = datetime.datetime(1970, 1, 1, tzinfo=timezone.utc)
UNIX_MIN_DATE_STRING = '1970-01-01T00:00:00Z'
UNIX_MAX_DATE_STRING = '2038-01-19T03:14:07Z'


def parse_datetime_to_epoch(datestamp, magnitude=1.0):
    """
    Convert an ISO-8601 datetime string to a Unix epoch timestamp in some magnitude.

    By default, returns seconds.
    """
    parsed_datetime = parse_lms_api_datetime(datestamp)
    time_since_epoch = parsed_datetime - UNIX_EPOCH
    return int(time_since_epoch.total_seconds() * magnitude)


def parse_datetime_to_epoch_millis(datestamp):
    """
    Convert an ISO-8601 datetime string to a Unix epoch timestamp in milliseconds.
    """
    return parse_datetime_to_epoch(datestamp, magnitude=1000.0)


def current_time_is_in_interval(start, end):
    """
    Determine whether the current time is on the interval [start, end].
    """
    interval_start = parse_lms_api_datetime(start or UNIX_MIN_DATE_STRING)
    interval_end = parse_lms_api_datetime(end or UNIX_MAX_DATE_STRING)
    return interval_start <= timezone.now() <= interval_end
