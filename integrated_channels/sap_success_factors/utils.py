"""
Utilities for Enterprise Integrated Channel SAP SuccessFactors.
"""
from __future__ import absolute_import, unicode_literals

import datetime
import json
import os
from logging import getLogger

from django.apps import apps
from django.utils import timezone
from six.moves.urllib.parse import urlunparse  # pylint: disable=import-error,wrong-import-order

from enterprise.django_compatibility import reverse
from enterprise.lms_api import parse_lms_api_datetime
from integrated_channels.integrated_channel.course_metadata import BaseCourseExporter


LOGGER = getLogger(__name__)
COURSE_URL_SCHEME = os.environ.get('SUCCESSFACTORS_COURSE_EXPORT_DEFAULT_URL_SCHEME', 'https')
UNIX_EPOCH = datetime.datetime(1970, 1, 1, tzinfo=timezone.utc)
UNIX_MIN_DATE_STRING = '1970-01-01T00:00:00Z'
UNIX_MAX_DATE_STRING = '2038-01-19T03:14:07Z'
SUCCESSFACTORS_OCN_LANGUAGE_CODES = {
    "ms": {
        "_": "Malay"
    },
    "ar": {
        "_": "Arabic"
    },
    "bg": {
        "_": "Bulgarian"
    },
    "cs": {
        "_": "Czech"
    },
    "cy": {
        "_": "Welsh"
    },
    "da": {
        "_": "Danish"
    },
    "de": {
        "_": "German"
    },
    "el": {
        "_": "Greek"
    },
    "en": {
        "ca": "English Canadian",
        "gb": "English United Kingdom",
        "_": "English"
    },
    "es": {
        "mx": "Spanish Mexican",
        "_": "Spanish"
    },
    "fi": {
        "_": "Finnish"
    },
    "fr": {
        "ca": "French Canadian",
        "_": "French"
    },
    "hi": {
        "_": "Hindi"
    },
    "hr": {
        "_": "Croatian"
    },
    "hu": {
        "_": "Hungarian"
    },
    "in": {
        "_": "Indonesian"
    },
    "it": {
        "_": "Italian"
    },
    "iw": {
        "_": "Hebrew"
    },
    "ja": {
        "_": "Japanese"
    },
    "ko": {
        "_": "Korean"
    },
    "nl": {
        "_": "Dutch"
    },
    "no": {
        "_": "Norwegian"
    },
    "pl": {
        "_": "Polish"
    },
    "pt": {
        "br": "Brazilian Portuguese",
        "_": "Portuguese"
    },
    "ro": {
        "_": "Romanian"
    },
    "ru": {
        "_": "Russian"
    },
    "sk": {
        "_": "Slovak"
    },
    "sl": {
        "_": "Slovenian"
    },
    "sr": {
        "_": "Serbian"
    },
    "sv": {
        "_": "Swedish"
    },
    "th": {
        "_": "Thai"
    },
    "tr": {
        "_": "Turkish"
    },
    "uk": {
        "_": "Ukrainian"
    },
    "vi": {
        "_": "Vietnamese"
    },
    "zh": {
        "hk": "Chinese Hong Kong",
        "tw": "Chinese Taiwan",
        "_": "Chinese"
    }
}


class SapCourseExporter(BaseCourseExporter):  # pylint: disable=abstract-method
    """
    Class to provide data transforms for SAP SuccessFactors course export task.
    """

    CHUNK_PAGE_LENGTH = 1000

    def __init__(self, user, plugin_configuration):
        super(SapCourseExporter, self).__init__(user, plugin_configuration)

    def get_serialized_data_blocks(self):
        """
        Return serialized blocks of data representing the courses to be POSTed, 1000 at a time.

        Yields:
            bytes: JSON-serialized course metadata structure
            int: Number of records in this batch
        """
        location = 0
        total_course_count = len(self.courses)
        while (location < total_course_count) or not location:
            this_batch = self.courses[location:location+self.CHUNK_PAGE_LENGTH]
            location += self.CHUNK_PAGE_LENGTH
            yield (
                json.dumps({'ocnCourses': this_batch}, sort_keys=True).encode('utf-8'),
                len(this_batch)
            )

    data_transform = {
        'courseID': lambda x: x['key'],
        'providerID': lambda x: apps.get_model(
            'sap_success_factors',
            'SAPSuccessFactorsGlobalConfiguration'
        ).current().provider_id,
        'status': lambda x: 'ACTIVE' if x['availability'] == 'Current' else 'INACTIVE',
        'title': lambda x: [
            {
                'locale': transform_language_code(x['content_language']),
                'value': x['title']
            },
        ],
        'description': lambda x: [
            {
                'locale': transform_language_code(x['content_language']),
                'value': x['full_description'] or x['short_description'] or '',
            },
        ],
        'thumbnailURI': lambda x: (x['image']['src'] or ''),
        'content': lambda x: [
            {
                'providerID': apps.get_model(
                    'sap_success_factors',
                    'SAPSuccessFactorsGlobalConfiguration'
                ).current().provider_id,
                'launchURL': get_course_track_selection_url(x['enterprise_customer'], x['key']),
                'contentTitle': 'Course Description',
                'contentID': x['key'],
                'launchType': 3,
                'mobileEnabled': x['mobile_available'],
            }
        ],
        'price': lambda x: [],
        'schedule': lambda x: [
            {
                'startDate': parse_datetime_to_epoch(x['start'] or UNIX_MIN_DATE_STRING),
                'endDate': parse_datetime_to_epoch(x['end'] or UNIX_MAX_DATE_STRING),
                'active': current_time_is_in_interval(x['start'], x['end']),
            }
        ],
        'revisionNumber': lambda x: 1,
    }


def get_course_track_selection_url(enterprise_customer, course_id):
    """
    Given an EnterpriseCustomer and a course ID, craft a URL that links to the track selection page for that course.

    Args:
        enterprise_customer (EnterpriseCustomer): The EnterpriseCustomer that a URL needs to be built for
        course_id (str): The string identifier of the course in question
    """
    netloc = enterprise_customer.site.domain
    scheme = COURSE_URL_SCHEME
    path = reverse('course_modes_choose', args=[course_id])
    return urlunparse((scheme, netloc, path, None, None, None))


def parse_datetime_to_epoch(datestamp):
    """
    Convert an ISO-8601 datetime string to a Unix epoch timestamp in milliseconds.
    """
    parsed_datetime = parse_lms_api_datetime(datestamp)
    time_since_epoch = parsed_datetime - UNIX_EPOCH
    return int(time_since_epoch.total_seconds() * 1000)


def current_time_is_in_interval(start, end):
    """
    Determine whether the current time is on the interval [start, end].
    """
    interval_start = parse_lms_api_datetime(start or UNIX_MIN_DATE_STRING)
    interval_end = parse_lms_api_datetime(end or UNIX_MAX_DATE_STRING)
    return interval_start <= timezone.now() <= interval_end


def transform_language_code(code):
    """
    Transform an ISO language code (for example, en-us) into a language name
    in the format read by SuccessFactors.
    """
    if code is None:
        return 'English'
    components = code.split('-')
    language_code = components[0]
    if len(components) == 2:
        country_code = components[1]
    elif len(components) == 1:
        country_code = '_'
    else:
        raise ValueError('Language codes may only have up to two components. Could not parse: {}'.format(code))

    if language_code not in SUCCESSFACTORS_OCN_LANGUAGE_CODES:
        LOGGER.warning('Language "%s" is not supported by SuccessFactors. Sending English by default.', language_code)
        return 'English'

    language_family = SUCCESSFACTORS_OCN_LANGUAGE_CODES[language_code]
    language_name = language_family.get(country_code, language_family['_'])
    return language_name
