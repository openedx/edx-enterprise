# -*- coding: utf-8 -*-
"""
Course metadata exporter for Enterprise Integrated Channel SAP SuccessFactors.
"""

from __future__ import absolute_import, unicode_literals

import json
import os
from logging import getLogger

from integrated_channels.integrated_channel.exporters.course_metadata import CourseExporter
from integrated_channels.sap_success_factors.constants import SUCCESSFACTORS_OCN_LANGUAGE_CODES
from integrated_channels.utils import (
    UNIX_MAX_DATE_STRING,
    UNIX_MIN_DATE_STRING,
    current_time_is_in_interval,
    parse_datetime_to_epoch_millis,
)

LOGGER = getLogger(__name__)
COURSE_URL_SCHEME = os.environ.get('SUCCESSFACTORS_COURSE_EXPORT_DEFAULT_URL_SCHEME', 'https')


class SapSuccessFactorsCourseExporter(CourseExporter):  # pylint: disable=abstract-method
    """
    Class to provide data transforms for SAP SuccessFactors course metadata export task.
    """

    CHUNK_PAGE_LENGTH = 500
    STATUS_ACTIVE = 'ACTIVE'
    STATUS_INACTIVE = 'INACTIVE'

    def export(self):
        """
        Return serialized blocks of data representing the courses to be POSTed, 1000 at a time.

        Yields:
            bytes: JSON-serialized course metadata structure
        """
        location = 0
        total_course_count = len(self.courses)
        while (location < total_course_count) or not location:
            this_batch = self.courses[location:location+self.CHUNK_PAGE_LENGTH]
            location += self.CHUNK_PAGE_LENGTH
            yield json.dumps({'ocnCourses': this_batch}, sort_keys=True).encode('utf-8'), 'POST'

    @property
    def data(self):
        """
        Return a transformed set of data ready to be exported.
        """
        return {
            'courseID': self.transform_course_id,
            'providerID': self.transform_provider_id,
            'status': self.transform_status,
            'title': self.transform_title,
            'description': self.transform_description,
            'thumbnailURI': self.transform_thumbnail_uri,
            'content': self.transform_content,
            'price': self.transform_price,
            'schedule': self.transform_schedule,
            'revisionNumber': self.transform_revision_number,
        }

    def transform_language_code(self, code):
        """
        Transform an ISO language code (for example, en-us) into a language name in the format read by SuccessFactors.
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
            LOGGER.warning('Language [%s] is not supported by SAPSF. Sending English by default.', language_code)
            return 'English'

        language_family = SUCCESSFACTORS_OCN_LANGUAGE_CODES[language_code]
        language_name = language_family.get(country_code, language_family['_'])
        return language_name

    def transform_course_id(self, course_run):
        """
        Return the transformed version of the course ID.
        """
        return course_run['key']

    def transform_provider_id(self, course_run):  # pylint: disable=unused-argument
        """
        Return the transformed version of the provider ID.
        """
        return self.enterprise_configuration.provider_id

    def transform_status(self, course_run):
        """
        Return the transformed version of the course status.
        """
        return (
            self.STATUS_ACTIVE
            if course_run['availability'] in [
                self.AVAILABILITY_CURRENT, self.AVAILABILITY_STARTING_SOON, self.AVAILABILITY_UPCOMING
            ] else self.STATUS_INACTIVE
        )

    def transform_title(self, course_run):
        """
        Return the transformed version of the course title, as well as the locale
        """
        return [{
            'locale': self.transform_language_code(course_run.get('content_language')),
            'value':  self.format_title(course_run)
        }]

    def transform_description(self, course_run):
        """
        Return the transformed version of the course description, as well as the locale.
        """
        return [{
            'locale': self.transform_language_code(course_run.get('content_language')),
            'value': (
                (course_run.get('full_description') or '')
                or (course_run.get('short_description') or '')
                or (course_run.get('title') or '')
            )
        }]

    def transform_thumbnail_uri(self, course_run):
        """
        Return the transformed version of the course's thumbnail URI.
        """
        image = course_run.get('image') or {}
        return image.get('src') or ''

    def transform_content(self, course_run):
        """
        Return the transformed version of the course content.

        Note that this is not actually course *content* per say, but rather just metadata.
        SAPSF expects the "content" key for this metadata, however, so we name the function
        "transform_content" for consistency.
        """
        return [{
            'providerID': self.enterprise_configuration.provider_id,
            'launchURL': self.get_launch_url(
                course_run['enterprise_customer'],
                course_run['key'],
                course_run.get('enrollment_url') or ''
            ),
            'contentTitle': self.format_title(course_run),
            'contentID': course_run['key'],
            'launchType': 3,
            'mobileEnabled': course_run.get('mobile_available', 'false')
        }]

    def transform_price(self, course_run):  # pylint: disable=unused-argument
        """
        Return the transformed version of the course price.
        """
        return []

    def transform_schedule(self, course_run):
        """
        Return the transformed version of the course schedule.
        """
        start = course_run.get('start') or UNIX_MIN_DATE_STRING
        end = course_run.get('end') or UNIX_MAX_DATE_STRING
        return [{
            'startDate': parse_datetime_to_epoch_millis(start),
            'endDate': parse_datetime_to_epoch_millis(end),
            'active': current_time_is_in_interval(start, end)
        }]

    def transform_revision_number(self, course_run):  # pylint: disable=unused-argument
        """
        Return the transformed version of the course revision number.
        """
        return 1

    def resolve_removed_courses(self, previous_audit_summary):  # pylint: disable=arguments-differ
        """
        Ensures courses that are no longer in the catalog get properly marked as inactive.

        Args:
            previous_audit_summary (dict): The previous audit summary from the last course export.

        Returns:
            An audit summary of courses with information about their presence in the catalog and current status.
        """
        if self.removed_courses_resolved:
            return {}

        new_audit_summary = {}
        new_courses = []

        for course in self.courses:
            course_key = course['courseID']
            course_status = course['status']

            # Remove the key from previous audit summary so we can process courses that are no longer present,
            # and keep course records for all previously pushed courses and new, active courses.
            if previous_audit_summary.pop(course_key, None) or course_status == self.STATUS_ACTIVE:
                new_courses.append(course)
                new_audit_summary[course_key] = {
                    'in_catalog': True,
                    'status': course_status,
                }

        for course_key, summary in previous_audit_summary.items():
            # Add a course payload to new_courses so that courses no longer in the catalog are marked inactive.
            if summary['status'] == self.STATUS_ACTIVE and summary['in_catalog']:
                new_courses.append(self.get_course_metadata_for_inactivation(
                    course_key,
                    self.enterprise_customer,
                    self.enterprise_configuration.provider_id
                ))

                new_audit_summary[course_key] = {
                    'in_catalog': False,
                    'status': self.STATUS_INACTIVE,
                }

        self.courses = new_courses
        self.removed_courses_resolved = True
        return new_audit_summary

    def get_launch_url(self, enterprise_customer, course_id, enrollment_url=None):
        """
        Given an EnterpriseCustomer and a course ID, determine the appropriate launch url.

        Args:
            enterprise_customer (EnterpriseCustomer): The EnterpriseCustomer that a URL needs to be built for
            course_id (str): The string identifier of the course in question
            enrollment_url (str): Enterprise landing page url for the given course from enterprise courses API
        """
        return enrollment_url or enterprise_customer.get_course_run_enrollment_url(course_id)

    def get_course_metadata_for_inactivation(self, course_id, enterprise_customer, provider_id):
        """
        Provide the minimal course metadata structure for updating a course to be inactive.
        """
        return {
            'courseID': course_id,
            'providerID': provider_id,
            'status': self.STATUS_INACTIVE,
            'title': [
                {
                    'locale': self.transform_language_code(None),
                    'value': course_id
                },
            ],
            'content': [
                {
                    'providerID': provider_id,
                    'launchURL': self.get_launch_url(enterprise_customer, course_id),
                    'contentTitle': 'Course Description',
                    'launchType': 3,
                    'contentID': course_id,
                }
            ],
        }
