# -*- coding: utf-8 -*-
"""
Content metadata exporter for Degreed.
"""

from logging import getLogger

from enterprise.utils import get_closest_course_run, get_course_run_duration_info, parse_datetime_handle_invalid
from integrated_channels.integrated_channel.exporters.content_metadata import ContentMetadataExporter
from integrated_channels.utils import generate_formatted_log, get_image_url, strip_html_tags

LOGGER = getLogger(__name__)


class Degreed2ContentMetadataExporter(ContentMetadataExporter):
    """
    Degreed2 implementation of ContentMetadataExporter.
    """

    CHUNK_PAGE_LENGTH = 1000
    SHORT_STRING_LIMIT = 255
    LONG_STRING_LIMIT = 2000

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
        return 'Days'

    def transform_duration(self, content_metadata_item):
        """
        Returns: duration in days
        """
        if content_metadata_item.get('content_type') == 'courserun':
            start = content_metadata_item.get('start')
            end = content_metadata_item.get('end')
        elif content_metadata_item.get('content_type') == 'course':
            course_runs = content_metadata_item.get('course_runs')
            if course_runs:
                course_run = get_closest_course_run(course_runs)
                if course_run:
                    start = course_run.get('start')
                    end = course_run.get('end')
                else:
                    LOGGER.error(
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
                LOGGER.error(
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

        start_date = parse_datetime_handle_invalid(start)
        end_date = parse_datetime_handle_invalid(end)
        if not start_date or not end_date:
            LOGGER.error(
                generate_formatted_log(
                    self.enterprise_configuration.channel_code(),
                    self.enterprise_configuration.enterprise_customer.uuid,
                    None,
                    None,
                    'Failed to find valid start/end dates, so duration is going to be set to 0. '
                    f'Course item was {content_metadata_item} '
                    f'Parsed Start was: {start_date}, End was: {end_date}'
                )
            )
            return 0
        return (end_date - start_date).days

    def transform_description(self, content_metadata_item):
        """
        Return the transformed version of the course description.

        We choose one value out of the course's full description, short description, and title
        depending on availability and length limits.
        """
        course_runs = content_metadata_item.get('course_runs')
        duration_info = get_course_run_duration_info(
            get_closest_course_run(course_runs)
        ) if course_runs else ''
        full_description = content_metadata_item.get('full_description') or ''
        if full_description and 0 < len(full_description + duration_info) <= self.LONG_STRING_LIMIT:
            description = full_description
        else:
            description = content_metadata_item.get('short_description') or content_metadata_item.get('title') or ''
        if description:
            description = "{duration_info}{description}".format(duration_info=duration_info, description=description)
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
