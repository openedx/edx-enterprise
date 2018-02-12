# -*- coding: utf-8 -*-
"""
Content metadata exporter for SAP SuccessFactors.
"""

from __future__ import absolute_import, unicode_literals

from logging import getLogger

from integrated_channels.integrated_channel.exporters.content_metadata import ContentMetadataExporter


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
        return [{
            'locale': 'English',
            'value':  content_metadata_item['title']
        }]

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
            'contentID': content_metadata_item['key'],
            'launchType': 3,  # This tells SAPSF to launch the course in a new browser window.
            'mobileEnabled': 'true'
        }]

    def transform_revision_number(self, content_metadata_item):  # pylint: disable=unused-argument
        """
        Return the revision number.
        """
        return 1
