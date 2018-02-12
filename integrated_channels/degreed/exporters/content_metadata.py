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

    DATA_TRANSFORM_MAPPING = {
        'contentId': 'key',
        'title': 'title',
        'description': 'description',
        'imageUrl': 'image',
        'url': 'enrollment_url',
    }

    def transform_description(self, content_metadata_item):
        """
        Return the description of the content item.
        """
        return [{
            'locale': 'English',
            'value': (
                content_metadata_item['full_description'] or
                content_metadata_item['short_description'] or
                content_metadata_item['title'] or
                ''
            )
        }]

    def transform_image(self, content_metadata_item):
        """
        Return the image URI of the content item.
        """
        return (content_metadata_item['image'] or {}).get('src', '') or ''
