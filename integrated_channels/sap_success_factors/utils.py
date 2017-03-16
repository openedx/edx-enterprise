"""
Utilities for Enterprise Integrated Channel SAP SuccessFactors.
"""
from __future__ import absolute_import, unicode_literals

import datetime
import json

from django.apps import apps

from enterprise.lms_api import parse_lms_api_datetime
from integrated_channels.integrated_channel.course_metadata import BaseCourseExporter


UNIX_EPOCH = datetime.datetime(1970, 1, 1)
UNIX_MIN_DATE_STRING = '1970-01-01T00:00:00Z'
UNIX_MAX_DATE_STRING = '2038-01-19T03:14:07Z'


class SapCourseExporter(BaseCourseExporter):
    """
    Class to provide data transforms for SAP SuccessFactors course export task.
    """

    def __init__(self, user, plugin_configuration):
        super(SapCourseExporter, self).__init__(user, plugin_configuration)

    def get_serialized_data(self):
        final_structure = {
            'ocnCourses': self.courses
        }
        return json.dumps(final_structure, sort_keys=True).encode('utf-8')

    data_transform = {
        'courseID': lambda x: x['key'],
        'providerID': lambda x: apps.get_model(
            'sap_success_factors',
            'SAPSuccessFactorsGlobalConfiguration'
        ).current().provider_id,
        'status': lambda x: 'ACTIVE' if x['availability'] == 'Current' else 'INACTIVE',
        'title': lambda x: [
            {
                'locale': 'English',
                'value': x['title']
            },
        ],
        'description': lambda x: [
            {
                'locale': 'English',
                'value': x['full_description'] or '',
            },
        ],
        'thumbnailURI': lambda x: (x['image']['src'] or ''),
        'content': lambda x: [
            {
                'providerID': apps.get_model(
                    'sap_success_factors',
                    'SAPSuccessFactorsGlobalConfiguration'
                ).current().provider_id,
                'launchURL': x['marketing_url'] or '',
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
                'duration': '',
            }
        ],
        'revisionNumber': lambda x: 1,
        'duration': lambda x: '',
    }


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
    return interval_start <= datetime.datetime.now() <= interval_end
