# -*- coding: utf-8 -*-
"""
Content metadata exporter for SAP SuccessFactors.
"""

from __future__ import absolute_import, unicode_literals

from logging import getLogger

from django.utils.translation import ugettext_lazy as _

from enterprise.api_client.lms import parse_lms_api_datetime
from integrated_channels.integrated_channel.exporters.content_metadata import ContentMetadataExporter
from integrated_channels.sap_success_factors.exporters.utils import (
    course_available_for_enrollment,
    transform_language_code,
)
from integrated_channels.utils import (
    UNIX_MAX_DATE_STRING,
    UNIX_MIN_DATE_STRING,
    current_time_is_in_interval,
    parse_datetime_to_epoch_millis,
)

LOGGER = getLogger(__name__)


class SapSuccessFactorsContentMetadataExporter(ContentMetadataExporter):  # pylint: disable=abstract-method
    """
    SAP SuccessFactors implementation of ContentMetadataExporter.
    """

    DATA_TRANSFORM_MAPPING = {
        'courseID': 'key',
        'providerID': 'provider_id',
        'status': 'status',
        'title': 'title',
        'description': 'description',
        'thumbnailURI': 'image',
        'content': 'launch_points',
        'revisionNumber': 'revision_number',
        'schedule': 'schedule',
    }

    def transform_provider_id(self, content_metadata_item):  # pylint: disable=unused-argument
        """
        Return the provider ID from the integrated channel configuration.
        """
        return self.enterprise_configuration.provider_id

    def transform_status(self, content_metadata_item):  # pylint: disable=unused-argument
        """
        Return the status of the content item.
        """
        return 'ACTIVE'

    def transform_title(self, content_metadata_item):
        """
        Return the title of the content item.
        """
        title_with_locales = []

        for locale in self.enterprise_configuration.get_locales():
            title_with_locales.append({
                'locale': locale,
                'value':  content_metadata_item.get('title', '')
            })

        return title_with_locales

    def transform_description(self, content_metadata_item):
        """
        Return the description of the content item.
        """
        description_with_locales = []

        for locale in self.enterprise_configuration.get_locales():
            description_with_locales.append({
                'locale': locale,
                'value': (
                    content_metadata_item.get('full_description') or
                    content_metadata_item.get('short_description') or
                    content_metadata_item.get('title', '')
                )
            })

        return description_with_locales

    def transform_image(self, content_metadata_item):
        """
        Return the image URI of the content item.
        """
        image_url = ''
        if content_metadata_item['content_type'] in ['course', 'program']:
            image_url = content_metadata_item.get('card_image_url')
        elif content_metadata_item['content_type'] == 'courserun':
            image_url = content_metadata_item.get('image_url')

        return image_url

    def transform_launch_points(self, content_metadata_item):
        """
        Return the content metadata item launch points.

        SAPSF allows you to transmit an arry of content launch points which
        are meant to represent sections of a content item which a learner can
        launch into from SAPSF. Currently, we only provide a single launch
        point for a content item.
        """
        return [{
            'providerID': self.enterprise_configuration.provider_id,
            'launchURL': content_metadata_item['enrollment_url'],
            'contentTitle': content_metadata_item['title'],
            'contentID': self.get_content_id(content_metadata_item),
            'launchType': 3,  # This tells SAPSF to launch the course in a new browser window.
            'mobileEnabled': self.is_mobile_enabled(content_metadata_item)
        }]

    def transform_revision_number(self, content_metadata_item):  # pylint: disable=unused-argument
        """
        Return the revision number.
        """
        return 1

    def transform_schedule(self, content_metadata_item):  # pylint: disable=unused-argument
        """
        Return the schedule of the content item.
        """
        return []

    def transform_courserun_title(self, content_metadata_item):
        """
        Return the title of the courserun content item.
        """
        title = content_metadata_item.get('title') or ''
        course_run_start = content_metadata_item.get('start')

        if course_run_start:
            if course_available_for_enrollment(content_metadata_item):
                title += ' ({starts}: {:%B %Y})'.format(
                    parse_lms_api_datetime(course_run_start),
                    starts=_('Starts')
                )
            else:
                title += ' ({:%B %Y} - {enrollment_closed})'.format(
                    parse_lms_api_datetime(course_run_start),
                    enrollment_closed=_('Enrollment Closed')
                )

        title_with_locales = []
        content_metadata_language_code = transform_language_code(content_metadata_item.get('content_language', ''))
        for locale in self.enterprise_configuration.get_locales(default_locale=content_metadata_language_code):
            title_with_locales.append({
                'locale': locale,
                'value':  title
            })

        return title_with_locales

    def transform_courserun_description(self, content_metadata_item):
        """
        Return the description of the courserun content item.
        """
        description_with_locales = []
        content_metadata_language_code = transform_language_code(content_metadata_item.get('content_language', ''))
        for locale in self.enterprise_configuration.get_locales(default_locale=content_metadata_language_code):
            description_with_locales.append({
                'locale': locale,
                'value': (
                    content_metadata_item['full_description'] or
                    content_metadata_item['short_description'] or
                    content_metadata_item['title'] or
                    ''
                )
            })

        return description_with_locales

    def transform_courserun_schedule(self, content_metadata_item):
        """
        Return the schedule of the courseun content item.
        """
        start = content_metadata_item.get('start') or UNIX_MIN_DATE_STRING
        end = content_metadata_item.get('end') or UNIX_MAX_DATE_STRING
        return [{
            'startDate': parse_datetime_to_epoch_millis(start),
            'endDate': parse_datetime_to_epoch_millis(end),
            'active': current_time_is_in_interval(start, end)
        }]

    def transform_program_key(self, content_metadata_item):
        """
        Return the identifier of the program content item.
        """
        return content_metadata_item['uuid']

    def get_content_id(self, content_metadata_item):
        """
        Return the id for the given content_metadata_item, `uuid` for programs or `key` for other content
        """
        content_id = content_metadata_item.get('key', '')
        if content_metadata_item['content_type'] == 'program':
            content_id = content_metadata_item.get('uuid', '')
        return content_id

    def is_mobile_enabled(self, content_metadata_item):
        """
        Return `True` if mobile is available for the active, otherwise `False`
        """
        return content_metadata_item.get('mobile_available', False)
