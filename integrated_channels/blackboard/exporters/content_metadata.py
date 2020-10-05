"""
Content metadata exporter for Canvas
"""

from logging import getLogger

from integrated_channels.integrated_channel.exporters.content_metadata import ContentMetadataExporter

LOGGER = getLogger(__name__)


class BlackboardContentMetadataExporter(ContentMetadataExporter):
    """
        Blackboard implementation of ContentMetadataExporter.
    """
    DATA_TRANSFORM_MAPPING = {
        'name': 'title',
        'externalId': 'key',
        'description': 'full_description',
        'courseId': 'key',
    }
