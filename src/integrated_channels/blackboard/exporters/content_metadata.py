"""
Content metadata exporter for Canvas
"""

from logging import getLogger

from integrated_channels.integrated_channel.exporters.content_metadata import ContentMetadataExporter

LOGGER = getLogger(__name__)
BLACKBOARD_COURSE_CONTENT_NAME = 'edX Course Details'


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

    DESCRIPTION_TEXT_TEMPLATE = "<a href={enrollment_url} target=_blank>Go to edX course page</a><br/>"
    LARGE_DESCRIPTION_TEXT_TEMPLATE = "<a href={enrollment_url} style='font-size:150%' target=_blank>" \
                                      "Go to edX course page</a><br/>"

    COURSE_TITLE_TEMPLATE = '<h1 style="font-size:xxx-large; margin-bottom:0; margin-top:0">{title}</h1>'

    COURSE_DESCRIPTION_TEMPLATE = '<p style="width:60%;">{description}</p>'

    COURSE_CONTENT_IMAGE_TEMPLATE = '<img src={image_url} width="30%" height="25%" border="40px"/>'

    COURSE_CONTENT_BODY_TEMPLATE = '<div><div style="display: inline-block">' \
                                   '{course_title}{large_description_text}<hr/></div>' \
                                   '<br/>{course_content_image}' \
                                   '<br/><br/><br/>{course_description}' \
                                   '<br/>{description_text}</div>'.format(
                                       course_title=COURSE_TITLE_TEMPLATE,
                                       large_description_text=LARGE_DESCRIPTION_TEXT_TEMPLATE,
                                       course_content_image=COURSE_CONTENT_IMAGE_TEMPLATE,
                                       course_description=COURSE_DESCRIPTION_TEMPLATE,
                                       description_text=DESCRIPTION_TEXT_TEMPLATE,
                                   )

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
            'title': BLACKBOARD_COURSE_CONTENT_NAME,
            'availability': 'Yes',
            'contentHandler': {
                'id': 'resource/x-bb-document',
            },
            'body': self.COURSE_CONTENT_BODY_TEMPLATE.format(
                title=title,
                description=content_metadata_item.get('full_description', None),
                image_url=content_metadata_item.get('image_url', None),
                enrollment_url=content_metadata_item.get('enrollment_url', None)
            )
        }
