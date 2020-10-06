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
        'description': 'description',
        'courseId': 'key',
    }

    DESCRIPTION_TEXT_TEMPLATE = "<a href={enrollment_url}>Go to edX course page</a><br />"

    def transform_description(self, content_metadata_item):
        """
        This will show a link to edX course on blackboard course description
        """
        enrollment_url = content_metadata_item.get('enrollment_url', None)
        url_link = self.DESCRIPTION_TEXT_TEMPLATE.format(enrollment_url=enrollment_url)
        short_description = content_metadata_item.get(
            'short_description', content_metadata_item.get('title', '')
        )
        description = "<p>{}</p><p>{}</p>".format(short_description, url_link)
        return description
