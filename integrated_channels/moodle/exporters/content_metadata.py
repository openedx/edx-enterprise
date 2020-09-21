"""
Content metadata exporter for Moodle
"""

from logging import getLogger

from dateutil.parser import parse

from integrated_channels.integrated_channel.exporters.content_metadata import ContentMetadataExporter

LOGGER = getLogger(__name__)


class MoodleContentMetadataExporter(ContentMetadataExporter):
    """
        Moodle implementation of ContentMetadataExporter.
    """
    DATA_TRANSFORM_MAPPING = {
        'fullname': 'title',
        'shortname': 'key',
        'idnumber': 'key',
        'summary': 'description',
        'startdate': 'start',
        'enddate': 'end',
        'categoryid': 'categoryid',
    }

    LONG_STRING_LIMIT = 2000

    def transform_description(self, content_metadata_item):
        """
        Return the course description and enrollment url as Moodle' syllabus body attribute.
        This will display in the Syllabus tab in Moodle.
        """
        enrollment_url = content_metadata_item.get('enrollment_url', None)
        base_description = "<a href={enrollment_url}>To edX Course Page</a><br />".format(
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

    def transform_categoryid(self, content_metadata_item):  # pylint: disable=unused-argument
        """
        Returns the Moodle category id configured in the model.
        ID 1 is Miscellaneous and is the default/basic category.
        """
        return self.enterprise_configuration.category_id or 1

    def transform_start(self, content_metadata_item):
        """
        Converts start from ISO date string to int (required for Moodle's "startdate" field)
        """
        start_date = content_metadata_item.get('start', None)
        if start_date:
            return int(parse(start_date).timestamp())
        return None

    def transform_end(self, content_metadata_item):
        """
        Converts end from ISO date string to int (required for Moodle's "enddate" field)
        """
        end_date = content_metadata_item.get('end', None)
        if end_date:
            return int(parse(end_date).timestamp())
        return None
