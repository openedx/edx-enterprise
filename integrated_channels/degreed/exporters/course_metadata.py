# -*- coding: utf-8 -*-
"""
Course metadata exporter for Enterprise Integrated Channel Degreed.
"""

from __future__ import absolute_import, unicode_literals

import json
from logging import getLogger

from integrated_channels.integrated_channel.exporters.course_metadata import CourseExporter

from django.conf import settings

from enterprise.utils import is_course_run_enrollable

LOGGER = getLogger(__name__)


class DegreedCourseExporter(CourseExporter):  # pylint: disable=abstract-method
    """
    Class to provide data transforms for Degreed course metadata export task.
    """

    CHUNK_PAGE_LENGTH = 1000
    SHORT_STRING_LIMIT = 255
    LONG_STRING_LIMIT = 2000

    STATUS_ACTIVE = 'ACTIVE'
    STATUS_INACTIVE = 'INACTIVE'

    def export(self):
        """
        Return serialized blocks of course metadata, which may be POST'd or DELETE'd depending on course enrollability.

        Yields:
            tuple: Contains the serialized course metadata JSON dump, and the method to be used.
                    - Method is one of 'POST' or 'DELETE'.
        """
        unenrollable_courses = []
        enrollable_courses = []
        for course_run in self.courses:
            # Course runs that have more than just the `contentId` key are considered enrollable.
            if len(course_run) > 1:
                enrollable_courses.append(course_run)
            else:
                unenrollable_courses.append(course_run)
        for course_group, method in [(unenrollable_courses, 'DELETE'), (enrollable_courses, 'POST')]:
            if course_group:
                yield (
                    json.dumps(
                        {
                            'courses': course_group,
                            'orgCode': self.enterprise_configuration.degreed_company_id,
                            'providerCode': self.enterprise_configuration.provider_id,
                        },
                        sort_keys=True
                    ).encode('utf-8'),
                    method
                )

    @property
    def data(self):
        """
        Return a transformed set of data ready to be exported.
        """
        return {
            'contentId': self.transform_course_id,
            'authors': self.transform_authors,
            'categoryTags': self.transform_category_tags,
            'url': self.transform_url,
            'imageUrl': self.transform_image_url,
            'videoUrl': self.transform_video_url,
            'title': self.transform_title,
            'description': self.transform_description,
            'difficulty': self.transform_difficulty,
            'duration': self.transform_duration,
            'publishDate': self.transform_publish_date,
            'format': self.transform_format,
            'institution': self.transform_institution,
            'costType': self.transform_cost_type,
            'language': self.transform_language_code
        }

    def transform(self, course_run):
        """
        Parse the provided course into the format natively supported by the provider.

        For Degreed, if a course run is unenrollable, it shouldn't be appearing in the
        upstream catalog. In that case, we just prepare a payload that is meant for deletion.
        The transmitter will do a check itself to see enrollability, and properly ``DELETE``
        the course.
        """
        LOGGER.info('Processing course run with ID [%s]', course_run['key'])
        LOGGER.debug('Parsing course run for [%s]: [%s]', self.enterprise_customer, json.dumps(course_run, indent=4))

        # Add the enterprise customer to the course run details so it can be used in the data transform
        course_run['enterprise_customer'] = self.enterprise_customer
        transformed_data = {}
        if is_course_run_enrollable(course_run):
            for key, transform in self.data.items():
                transformed_data[key] = transform(course_run) if transform is not None else course_run.get(key)
        else:
            # For courses that should be deleted, we just need their ID.
            transformed_data['contentId'] = self.transform_course_id(course_run)
        return transformed_data

    def transform_category_tags(self, course_run):  # pylint: disable=unused-argument
        """
        Return a transformed version of course tags.

        Note: no formal category tags for courses actually exist at this time. Update this when and if they do.
        """
        return course_run.get('tags') or []

    def transform_duration(self, course_run):
        """
        Return the transformed duration of the course.

        Degreed expects the value to be in minutes.
        """
        weeks_to_complete = course_run.get('weeks_to_complete') or 0
        return weeks_to_complete * 7 * 24 * 60

    def transform_publish_date(self, course_run):
        """
        Return the transformed version of the publish date for this course run.

        Example:
            2017-02-01T05:00:00Z -> 2017-02-01
        """
        # Instead of doing something fancy, since the first 10 characters will always be
        # of format yyyy-mm-dd, just get the first 10 characters.
        start = course_run.get('start') or ''
        return start[:10]

    def transform_institution(self, course_run):
        """
        Return the transformed version of the course institution.
        """
        institutions = course_run.get('owners')
        return institutions[0]['name'] if institutions else ''

    def transform_authors(self, course_run):
        """
        Return the array of author/instructor names for the course.
        """
        return [
            '{first_name} {last_name}'.format(
                first_name=instructor.get('given_name') or '',
                last_name=instructor.get('family_name') or '',
            ) for instructor in course_run.get('staff') or []
        ]

    def transform_language_code(self, course_run):
        """
        Return the ISO 639-1 language code that Degreed expects.

        Example:
            en-us -> en
            None -> en
        """
        code = course_run.get('content_language') or ''
        return code.split('-')[0] or 'en'

    def transform_course_id(self, course_run):
        """
        Return the transformed version of the course ID.
        """
        return course_run['key']

    def transform_cost_type(self, course_run):
        """
        Return the transformed version of the course enrollment cost type.

        One can use the course track to determine payment status. Values must be one of:
            - Subscription
            - Free
            - Paid

        We only really use the latter 2.
        """
        audit_modes = getattr(settings, 'ENTERPRISE_COURSE_ENROLLMENT_AUDIT_MODES', ['audit', 'honor'])
        return 'Free' if course_run.get('type') in audit_modes else 'Paid'

    def transform_title(self, course_run):
        """
        Return the transformed version of the course title.
        """
        return self.format_title(course_run)

    def transform_description(self, course_run):
        """
        Return the transformed version of the course description.

        We choose one value out of the course's full description, short description, and title
        depending on availability and length limits.
        """
        full_description = course_run.get('full_description') or ''
        if 0 < len(full_description) <= self.LONG_STRING_LIMIT:  # pylint: disable=len-as-condition
            return full_description
        return course_run.get('short_description') or course_run.get('title') or ''

    def transform_url(self, course_run):
        """
        Return the transformed version of the course's track selection URL.
        """
        return (
            course_run.get('enrollment_url')
            or course_run['enterprise_customer'].get_course_run_enrollment_url(course_run['key'])
        )

    def transform_image_url(self, course_run):
        """
        Return the transformed version of the course's image URL.
        """
        image = course_run.get('image') or {}
        return image.get('src') or ''

    def transform_video_url(self, course_run):
        """
        Return the transformed version of the course's video URL.
        """
        video = course_run.get('video') or {}
        return video.get('src') or ''

    def transform_difficulty(self, course_run):
        """
        Return the transformed difficulty.
        """
        return course_run.get('level_type') or ''

    def transform_format(self, course_run):
        """
        Return the transformed version of the course run format.

        Degreed expects one of the following values:
            - Instructor
            - Online
            - Virtual
            - Accredited
        """
        return 'Instructor' if course_run.get('pacing_type') == 'instructor_paced' else 'Online'
