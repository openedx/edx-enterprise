# -*- coding: utf-8 -*-
"""
Content metadata exporter for Degreed.
"""

from __future__ import absolute_import, unicode_literals

from logging import getLogger

from integrated_channels.integrated_channel.exporters.content_metadata import ContentMetadataExporter

LOGGER = getLogger(__name__)


class DegreedContentMetadataExporter(ContentMetadataExporter):  # pylint: disable=abstract-method
    """
    Degreed implementation of ContentMetadataExporter.
    """

    CHUNK_PAGE_LENGTH = 1000
    SHORT_STRING_LIMIT = 255
    LONG_STRING_LIMIT = 2000

    DATA_TRANSFORM_MAPPING = {
        'contentId': 'key',
        'title': 'title',
        'description': 'description',
        'imageUrl': 'image',
        'url': 'enrollment_url',
        'language': 'content_language'
    }

    def transform_description(self, content_metadata_item):
        """
        Return the transformed version of the course description.

        We choose one value out of the course's full description, short description, and title
        depending on availability and length limits.
        """
        full_description = content_metadata_item.get('full_description') or ''
        if 0 < len(full_description) <= self.LONG_STRING_LIMIT:  # pylint: disable=len-as-condition
            return full_description
        return content_metadata_item.get('short_description') or content_metadata_item.get('title') or ''

    def transform_courserun_content_language(self, content_metadata_item):
        """
        Return the ISO 639-1 language code that Degreed expects for coureseruns.

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
        image_url = ''
        if content_metadata_item['content_type'] in ['course', 'program']:
            image_url = content_metadata_item.get('card_image_url')
        elif content_metadata_item['content_type'] == 'courserun':
            image_url = content_metadata_item.get('image_url')

        return image_url

    def transform_program_key(self, content_metadata_item):
        """
        Return the identifier of the program content item.
        """
        return content_metadata_item['uuid']
