# -*- coding: utf-8 -*-
"""
Utilities common to different integrated channels.
"""

import base64
import math
import re
from datetime import datetime, timedelta
from itertools import islice
from logging import getLogger
from string import Formatter

import pytz
import requests
from six.moves import range

from django.utils import timezone
from django.utils.html import strip_tags

from enterprise.utils import parse_datetime_handle_invalid, parse_lms_api_datetime
from integrated_channels.catalog_service_utils import get_course_run_for_enrollment

UNIX_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
UNIX_MIN_DATE_STRING = '1970-01-01T00:00:00Z'
UNIX_MAX_DATE_STRING = '2038-01-19T03:14:07Z'

LOGGER = getLogger(__name__)


def convert_invalid_course_ids(course_id):
    """
    Regex check a course ID to see if it contains any invalid chars. If it does then encode the string, otherwise
    return the original course ID.
    """
    re2 = re.compile(r"[|<>.&%\s\\/\“]+")
    if re2.search(course_id):
        # If the course key contains any of the invalid chars, encode the key
        return encode_course_key_into_base64(course_id)
    return course_id


def encode_course_key_into_base64(edx_course_key):
    """
    Base64 encodes edx course key (string) into a form safe (string) for use with LMS such as Cornerstone
    e.g., Cornerstone does not allow some chars
    For Base64, the urlsafe version is used, since it only uses a pretty limited charset, minus the /
    edX course keys allow these chars `ALLOWED_ID_CHARS` per: opaque_keys/edx/locator.py
    """
    if edx_course_key is None:
        raise ValueError('Cannot process an undefined edx_course_key')
    if not edx_course_key.replace(' ', ''):
        raise ValueError('Cannot process a spaces-only edx_course_key')
    return base64.urlsafe_b64encode(edx_course_key.encode("utf-8")).decode('utf-8')


def decode_course_key_from_base64(lms_course_key):
    """
    Decodes the base64 urlsafe encoded lms_course_key, into an edX course key (string)
    """
    return base64.urlsafe_b64decode(lms_course_key).decode('utf-8')


def parse_datetime_to_epoch(datestamp, magnitude=1.0):
    """
    Convert an ISO-8601 datetime string to a Unix epoch timestamp in some magnitude.

    By default, returns seconds.
    """
    parsed_datetime = parse_lms_api_datetime(datestamp)
    time_since_epoch = parsed_datetime - UNIX_EPOCH
    return int(time_since_epoch.total_seconds() * magnitude)


def strip_html_tags(text, strip_entities=True):
    """
    Return (str): Text without any html tags and entities.

    Args:
        text (str): text having html tags
        strip_entities (bool): If set to True html entities are also stripped
    """
    text = strip_tags(text)
    if strip_entities:
        text = re.sub(r'&([a-zA-Z]{4,5}|#[0-9]{2,4});', '', text)
    return text


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


def convert_comma_separated_string_to_list(comma_separated_string):
    """
    Convert the comma separated string to a valid list.
    """
    return list(set(item.strip() for item in comma_separated_string.split(",") if item.strip()))


def get_image_url(content_metadata_item):
    """
    Return the image URI of the content item.
    """
    image_url = ''
    if content_metadata_item['content_type'] == 'program':
        image_url = content_metadata_item.get('card_image_url')
    elif content_metadata_item['content_type'] in ['course', 'courserun']:
        image_url = content_metadata_item.get('image_url')

    return image_url


def is_already_transmitted(transmission, enterprise_enrollment_id, grade, subsection_id=None):
    """
    Returns: Boolean indicating if completion date for given enrollment is already sent of not.

    Args:
        transmission: TransmissionAudit model to search enrollment in
        enterprise_enrollment_id: enrollment id
        grade: 'Pass' or 'Fail' status
        subsection_id (Optional): The id of the subsection, needed if transmitting assessment level grades as there can
        be multiple per course.
    """
    try:
        already_transmitted = transmission.objects.filter(
            enterprise_course_enrollment_id=enterprise_enrollment_id,
            error_message='',
            status__lt=400
        )
        if subsection_id:
            already_transmitted = already_transmitted.filter(subsection_id=subsection_id)

        latest_transmitted_tx = already_transmitted.latest('id')
        return latest_transmitted_tx and getattr(latest_transmitted_tx, 'grade', None) == grade
    except transmission.DoesNotExist:
        return False


def get_duration_from_estimated_hours(estimated_hours):
    """
    Return the duration in {hours}:{minutes}:00 corresponding to estimated hours as int or float.
    """
    if estimated_hours and isinstance(estimated_hours, (int, float)):
        fraction, whole_number = math.modf(estimated_hours)
        hours = "{:02d}".format(int(whole_number))
        minutes = "{:02d}".format(int(60 * fraction))
        duration = "{hours}:{minutes}:00".format(hours=hours, minutes=minutes)
        return duration

    return None


def get_subjects_from_content_metadata(content_metadata_item):
    """
    Returns a list of subject names for the content metadata item.

    Subjects in the content metadata item are represented by either:
      - a list of strings, e.g. ['Communication']
      - a list of objects, e.g. [{'name': 'Communication'}]

    Arguments:
        - content_metadata_item (dict): a dictionary for the content metadata item

    Returns:
        - list: a list of subject names as strings
    """
    metadata_subjects = content_metadata_item.get('subjects') or []
    subjects = set()

    for subject in metadata_subjects:
        if isinstance(subject, str):
            subjects.add(subject)
            continue

        subject_name = subject.get('name')
        if subject_name:
            subjects.add(subject_name)

    return list(subjects)


def generate_formatted_log(
    channel_name,
    enterprise_customer_uuid,
    lms_user_id,
    course_or_course_run_key,
    message
):
    """
    Formats and returns a standardized message for the integrated channels.
    'None' may be passed as a value to any format field, but all fields are mandatory to
    encourage log standardization.

    Arguments:
    - channel_name (str): The name of the integrated channel
    - enterprise_customer_uuid (str): UUID of the relevant EnterpriseCustomer
    - lms_user_id (str): The LMS User id (if applicable) related to the message
    - course_or_course_run_key (str): The course key (if applicable) for the message
    - message (str): The string to be formatted and logged

    """
    return '[integrated_channel:{channel_name}]'\
        '[integrated_channel_enterprise_customer_uuid:{enterprise_customer_uuid}]' \
        '[integrated_channel_lms_user:{lms_user_id}]'\
        '[integrated_channel_course_key:{course_or_course_run_key}] {message}'.format(
            enterprise_customer_uuid=enterprise_customer_uuid,
            channel_name=channel_name,
            message=message,
            lms_user_id=lms_user_id,
            course_or_course_run_key=course_or_course_run_key
        )


def refresh_session_if_expired(oauth_access_token_function, session=None, expires_at=None):
    """
    Instantiate a new session object for use in connecting with integrated channel.
    Or, return an updated session if provided session has expired.
    Suitable for use with oauth supporting servers that use bearer token: Canvas, Blackboard etc.

    Arguments:
        - oauth_access_token_function (function): access token fetch function
        - session (requests.Session): a session object. Pass None if creating new session
        - expires_at: the expiry date of the session if known. None is interpreted as expired.

    Each enterprise customer connecting to channel should have a single client session.
    Will only create a new session if token expiry has been reached
    If a new session is being created, closes the session first

    Returns (tuple) with values:
     - session: newly created session or an updated session (can be stored for later use)
     - expires_at: new expiry date to be stored for later use
    If session has not expired, or not updated for any reason, just returns the input values of
    session and expires_at
    """
    now = datetime.utcnow()
    if session is None or expires_at is None or now >= expires_at:
        # need new session if session expired, or not initialized
        if session:
            session.close()
        # Create a new session with a valid token
        oauth_access_token, expires_in = oauth_access_token_function()
        new_session = requests.Session()
        new_session.headers['Authorization'] = 'Bearer {}'.format(oauth_access_token)
        new_session.headers['content-type'] = 'application/json'
        # expiry expected after `expires_in` seconds
        if expires_in is not None:
            new_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        return new_session, new_expires_at
    return session, expires_at


def get_upgrade_deadline(course_run):
    """
    Returns upgrade_deadline of a verified seat if found. Otherwise returns None.
    """
    for seat in course_run.get('seats', []):
        if seat.get('type') == 'verified':
            return parse_datetime_handle_invalid(seat.get('upgrade_deadline'))
    return None


def is_course_completed(enterprise_enrollment, completed_date, is_passing, incomplete_count):
    '''
    For non audit, this requires passing and completed_date
    For audit enrollment, returns True if:
     - for non upgradable course:
        - no more non-gated content is left
     - for upgradable course:
        - the verified upgrade deadline has passed AND no more non-gated content is left
    '''
    if enterprise_enrollment.is_audit_enrollment:
        if incomplete_count is None:
            raise ValueError('Incomplete count is required if using audit enrollment')
        course_run = get_course_run_for_enrollment(enterprise_enrollment)
        upgrade_deadline = get_upgrade_deadline(course_run)
        if upgrade_deadline is None:
            return incomplete_count == 0
        else:
            # for upgradable course check deadline passed as well
            now = datetime.now(pytz.UTC)
            return incomplete_count == 0 and upgrade_deadline < now
    return completed_date is not None and is_passing
