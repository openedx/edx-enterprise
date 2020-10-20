"""
Content metadata exporter for Canvas
"""

from logging import getLogger

from integrated_channels.integrated_channel.exporters.content_metadata import ContentMetadataExporter

LOGGER = getLogger(__name__)
BLACKBOARD_COURSE_CONTENT_NAME = 'edX Integration'


class BlackboardContentMetadataExporter(ContentMetadataExporter):
    """
        Blackboard implementation of ContentMetadataExporter.
        Note: courseId is not being exported here (instead done in client during content send)
    """
    DATA_TRANSFORM_MAPPING = {
        'externalId': 'key',
        'course_metadata': 'course_metadata',
        'course_content_metadata': 'course_content_metadata',
        'course_child_content_metadata': 'course_child_content_metadata',
    }

    DESCRIPTION_TEXT_TEMPLATE = "<a href={enrollment_url}>Go to edX course page</a><br />"

    def transform_course_metadata(self, content_metadata_item):
        """
        Formats the metadata necessary to create a base course object in Blackboard
        """
        return {
            'name': content_metadata_item.get('title', None),
            'externalId': content_metadata_item.get('key', None),
            'description': self.DESCRIPTION_TEXT_TEMPLATE.format(
                enrollment_url=content_metadata_item.get('enrollment_url', None)
            )
        }

    def transform_course_content_metadata(self, content_metadata_item):  # pylint: disable=unused-argument
        """
        Formats the metadata necessary to create a course content object in Blackboard
        """
        return {
            'title': BLACKBOARD_COURSE_CONTENT_NAME,
            'position': 0,
            "contentHandler": {"id": "resource/x-bb-folder"}
        }

    def transform_course_child_content_metadata(self, content_metadata_item):
        """
        Formats the metadata necessary to create a course content object in Blackboard
        """
        title = content_metadata_item.get('title', None)
        return {
            'title': title,
            'availability': 'Yes',
            'contentHandler': {
                'id': 'resource/x-bb-externallink',
                'url': content_metadata_item.get('enrollment_url', None),
            },
            'body': '<div>{title}</div><div>{description}</div><img src={image_url} />'.format(
                title=title,
                description=content_metadata_item.get('full_description', None),
                image_url=content_metadata_item.get('image_url', None),
            )
        }
