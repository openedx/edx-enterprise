# -*- coding: utf-8 -*-
"""
Content metadata exporter for Degreed.
"""

from logging import getLogger

from enterprise.utils import get_closest_course_run, get_course_run_duration_info
from integrated_channels.integrated_channel.exporters.content_metadata import ContentMetadataExporter
from integrated_channels.utils import (
    generate_formatted_log,
    get_courserun_duration_in_hours,
    get_image_url,
    strip_html_tags,
)

LOGGER = getLogger(__name__)


class Degreed2ContentMetadataExporter(ContentMetadataExporter):
    """
    Degreed2 implementation of ContentMetadataExporter.
    """

    CHUNK_PAGE_LENGTH = 1000
    SHORT_STRING_LIMIT = 255
    LONG_STRING_LIMIT = 2000
    ELLIPSIS = '...'

    DATA_TRANSFORM_MAPPING = {
        'title': 'title',
        'summary': 'description',
        'image-url': 'image',
        'url': 'enrollment_url',
        'language': 'content_language',
        'external-id': 'key',
        'duration': 'duration',
        'duration-type': 'duration_type',
    }

    def transform_duration_type(self, content_metadata_item):  # pylint: disable=unused-argument
        return 'Hours'

    def transform_duration(self, content_metadata_item):
        """
        Returns: duration in days
        """
        if content_metadata_item.get('content_type') == 'courserun':
            return get_courserun_duration_in_hours(content_metadata_item)
        elif content_metadata_item.get('content_type') == 'course':
            course_runs = content_metadata_item.get('course_runs')
            if course_runs:
                course_run = get_closest_course_run(course_runs)
                if course_run:
                    return get_courserun_duration_in_hours(course_run)
                else:
                    LOGGER.warning(
                        generate_formatted_log(
                            self.enterprise_configuration.channel_code(),
                            self.enterprise_configuration.enterprise_customer.uuid,
                            None,
                            None,
                            'Cannot find a courserun, so duration being returned 0. '
                            f'Course item was {content_metadata_item} '
                        )
                    )
                    return 0
            else:
                LOGGER.warning(
                    generate_formatted_log(
                        self.enterprise_configuration.channel_code(),
                        self.enterprise_configuration.enterprise_customer.uuid,
                        None,
                        None,
                        'Cannot find even a single courserun, so duration being returned 0. '
                        f'Course item was {content_metadata_item} '
                    )
                )
                return 0
        else:
            return 0

    def transform_description(self, content_metadata_item):
        """
        Return the transformed version of the course description.

        We choose one value out of the course's full description, short description, and title
        depending on availability.
        """
        course_runs = content_metadata_item.get('course_runs')

        duration_info = get_course_run_duration_info(
            get_closest_course_run(course_runs)
        ) if course_runs else ''

        owner_names = ''
        owners = content_metadata_item.get('owners')
        if owners:
            owner_names = ', '.join([owner['name'] for owner in owners])
            if owner_names:
                owner_names = "[{}]: ".format(owner_names)

        description = (
            content_metadata_item.get('full_description')
            or content_metadata_item.get('short_description')
            or content_metadata_item.get('title')
            or '')

        if description:
            description = "{}{}{}".format(owner_names, duration_info, description)
            if len(description) > self.LONG_STRING_LIMIT:
                description = description[:self.LONG_STRING_LIMIT - len(self.ELLIPSIS)] + self.ELLIPSIS

        return strip_html_tags(description)

    def transform_courserun_content_language(self, content_metadata_item):
        """
        Return the ISO 639-1 language code that Degreed expects for course runs.

        Example:
            en-us -> en
            None -> en
        """
        code = content_metadata_item.get('content_language') or ''
        return code.split('-')[0] or 'en'

    def transform_content_language(self, content_metadata_item):  # pylint: disable=unused-argument
        """
        Return the ISO 639-1 language code that Degreed expects.

        Example:
            en-us -> en
            None -> en
        """
        # TODO: This needs to be implemented once we have richer data from the discovery service
        return 'en'

    def transform_image(self, content_metadata_item):
        """
        Return the image URI of the content item.
        """
        return get_image_url(content_metadata_item)

    def transform_program_key(self, content_metadata_item):
        """
        Return the identifier of the program content item.
        """
        return content_metadata_item['uuid']
