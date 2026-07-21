"""
Content metadata exporter for Canvas
"""

from datetime import datetime
from logging import getLogger

from integrated_channels.integrated_channel.exporters.content_metadata import ContentMetadataExporter

LOGGER = getLogger(__name__)


def convert_date_str(date_str):
    '''
    Returns formatted date string from ISO8601 format (e.g. 2011-01-01T01:00:10Z)
    to a human readable suitable for use in Canvas
    Return 'N/A' if input arg is None, or 'N/A'
    If format is not ISO8601, returns original string.
    '''
    if not date_str or date_str == 'N/A':
        return date_str
    try:
        start_date = datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%SZ')
        formatted_start_date = start_date.strftime('%a %b %d %Y %H:%M:%S')
    except ValueError:
        return date_str
    return formatted_start_date


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
        'indexed': 'indexed',
        'restrict_enrollments_to_course_dates': 'restrict_enrollments_to_course_dates',
    }
    SKIP_KEY_IF_NONE = True

    LONG_STRING_LIMIT = 2000

    def transform_restrict_enrollments_to_course_dates(self, content_metadata_item):  # pylint: disable=unused-argument
        '''
        This enforces the course to use the participation type of 'Course' rather than Term
        '''
        return True

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

        formatted_start_date = convert_date_str(content_metadata_item.get('start', 'N/A'))
        formatted_end_date = convert_date_str(content_metadata_item.get('end', 'N/A'))
        description = (f"{description} <br />"
                       f"<br />Starts: {formatted_start_date}"
                       f"<br />Ends: {formatted_end_date}")

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

    def transform_start(self, content_metadata_item):
        """
        Returns none if no start date is available (the case for courses),
        and the start date (the case for course run data)
        """
        return content_metadata_item.get('start', None)

    def transform_end(self, content_metadata_item):
        """
        Returns none if no end date is available (the case for courses),
         and the end date (the case for course run data)
        """
        return content_metadata_item.get('end', None)
