"""
Content metadata exporter for Canvas
"""

from logging import getLogger

from integrated_channels.integrated_channel.exporters.content_metadata import ContentMetadataExporter

LOGGER = getLogger(__name__)


class BlackboardContentMetadataExporter(ContentMetadataExporter):
    """
        Blackboard implementation of ContentMetadataExporter.
        Note: courseId is not being exported here (instead done in client during content send)
    """
    DATA_TRANSFORM_MAPPING = {
        'name': 'title',
        'externalId': 'key',
        'description': 'enrollment_url',
    }

    DESCRIPTION_TEXT_TEMPLATE = "<a href={enrollment_url}>Go to edX course page</a><br />"

    def transform_enrollment_url(self, content_metadata_item):
        """
        This will show a link to edX course on blackboard course description
        """
        enrollment_url = content_metadata_item.get('enrollment_url', None)
        url_link = self.DESCRIPTION_TEXT_TEMPLATE.format(enrollment_url=enrollment_url)
        return url_link
