"""
Content metadata exporter for Canvas
"""

from logging import getLogger

from integrated_channels.integrated_channel.exporters.content_metadata import ContentMetadataExporter

LOGGER = getLogger(__name__)


class CanvasContentMetadataExporter(ContentMetadataExporter):
    """
        Canvas implementation of ContentMetadataExporter.
    """
    DATA_TRANSFORM_MAPPING = {
        'name': 'title',
        'start_at': 'start',
        'end_at': 'end',
        'integration_id': 'key',
        'syllabus_body': 'description',
        'default_view': 'default_view',
        'image_url': 'image_url',
        'is_public': 'is_public',
        'self_enrollment': 'self_enrollment',
        'course_code': 'key',
        'indexed': 'indexed'
    }

    LONG_STRING_LIMIT = 2000

    def transform_description(self, content_metadata_item):
        """
        Return the course description and enrollment url as Canvas' syllabus body attribute.
        This will display in the Syllabus tab in Canvas.
        """
        enrollment_url = content_metadata_item.get('enrollment_url', None)
        base_description = "<a href={enrollment_url}>Go to edX course page</a><br />".format(
            enrollment_url=enrollment_url)
        full_description = content_metadata_item.get('full_description') or None
        if full_description and len(full_description + enrollment_url) <= self.LONG_STRING_LIMIT:
            description = "{base_description}{full_description}".format(
                base_description=base_description,
                full_description=full_description
            )
        else:
            short_description = content_metadata_item.get(
                'short_description', content_metadata_item.get('title', '')
            )
            description = "{base_description}{short_description}".format(
                base_description=base_description, short_description=short_description
            )

        return description

    def transform_default_view(self, content_metadata_item):  # pylint: disable=unused-argument
        """
        Sets the Home page view in Canvas. We're using Syllabus.
        """
        return 'syllabus'

    def transform_is_public(self, content_metadata_item):  # pylint: disable=unused-argument
        """
        Whether to make the course content visible to students by default. Note that setting this feature to false
        will not remove the course from discovery, but will rather remove all visible content from the course if
        any student attempts to access it.
        """
        return True

    def transform_self_enrollment(self, content_metadata_item):  # pylint: disable=unused-argument
        """
        Whether to allow students to self enroll. Helps students enroll via link or enroll button.
        """
        return True

    def transform_indexed(self, content_metadata_item):  # pylint: disable=unused-argument
        """
        Whether to make the course default to the public index or not.
        """
        return 1
