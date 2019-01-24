# -*- coding: utf-8 -*-
"""
Utilities common to different integrated channels.
"""

from __future__ import absolute_import, unicode_literals

import datetime
from itertools import islice
from string import Formatter

from six.moves import range

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


def chunks(dictionary, chunk_size):
    """
    Yield successive n-sized chunks from dictionary.
    """
    iterable = iter(dictionary)
    for __ in range(0, len(dictionary), chunk_size):
        yield {key: dictionary[key] for key in islice(iterable, chunk_size)}


def strfdelta(tdelta, fmt='{D:02}d {H:02}h {M:02}m {S:02}s', input_type='timedelta'):
    """
    Convert a datetime.timedelta object or a regular number to a custom-formatted string.

    This function works like the strftime() method works for datetime.datetime
    objects.

    The fmt argument allows custom formatting to be specified.  Fields can
    include seconds, minutes, hours, days, and weeks.  Each field is optional.

    Arguments:
        tdelta (datetime.timedelta, int): time delta object containing the duration or an integer
            to go with the input_type.
        fmt (str): Expected format of the time delta. place holders can only be one of the following.
            1. D to extract days from time delta
            2. H to extract hours from time delta
            3. M to extract months from time delta
            4. S to extract seconds from timedelta
        input_type (str):  The input_type argument allows tdelta to be a regular number instead of the
            default, which is a datetime.timedelta object.
            Valid input_type strings:
                1. 's', 'seconds',
                2. 'm', 'minutes',
                3. 'h', 'hours',
                4. 'd', 'days',
                5. 'w', 'weeks'
    Returns:
        (str): timedelta object interpolated into a string following the given format.

    Examples:
        '{D:02}d {H:02}h {M:02}m {S:02}s' --> '05d 08h 04m 02s' (default)
        '{W}w {D}d {H}:{M:02}:{S:02}'     --> '4w 5d 8:04:02'
        '{D:2}d {H:2}:{M:02}:{S:02}'      --> ' 5d  8:04:02'
        '{H}h {S}s'                       --> '72h 800s'
    """
    # Convert tdelta to integer seconds.
    if input_type == 'timedelta':
        remainder = int(tdelta.total_seconds())
    elif input_type in ['s', 'seconds']:
        remainder = int(tdelta)
    elif input_type in ['m', 'minutes']:
        remainder = int(tdelta) * 60
    elif input_type in ['h', 'hours']:
        remainder = int(tdelta) * 3600
    elif input_type in ['d', 'days']:
        remainder = int(tdelta) * 86400
    elif input_type in ['w', 'weeks']:
        remainder = int(tdelta) * 604800
    else:
        raise ValueError(
            'input_type is not valid. Valid input_type strings are: "timedelta", "s", "m", "h", "d", "w"'
        )

    f = Formatter()
    desired_fields = [field_tuple[1] for field_tuple in f.parse(fmt)]
    possible_fields = ('W', 'D', 'H', 'M', 'S')
    constants = {'W': 604800, 'D': 86400, 'H': 3600, 'M': 60, 'S': 1}
    values = {}

    for field in possible_fields:
        if field in desired_fields and field in constants:
            values[field], remainder = divmod(remainder, constants[field])

    return f.format(fmt, **values)
