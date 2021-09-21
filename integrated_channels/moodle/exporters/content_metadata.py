"""
Content metadata exporter for Moodle
"""
from datetime import timezone
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
        'shortname': 'shortname',
        'idnumber': 'key',
        'summary': 'description',
        'startdate': 'start',
        'enddate': 'end',
        'categoryid': 'categoryid',
    }

    LONG_STRING_LIMIT = 1700  # Actual maximum value we can support for any individual course
    SKIP_KEY_IF_NONE = True

    def transform_shortname(self, content_metadata_item):
        """
        We're prefixing Title to the key to make shortname a little nicer in Moodle's UI.
        But because we use key elsewhere, I mapped this to itself
        so it doesn't override all "key" references
        """
        return '{} ({})'.format(
            content_metadata_item.get('title'),
            content_metadata_item.get('key')
        )

    def transform_title(self, content_metadata_item):
        """
        Returns the course title with all organizations (partners) appended in parantheses
        Returned format is: courseTitle - via edX.org (Partner)
        """
        formatted_orgs = []
        for org in content_metadata_item.get('organizations', []):
            split_org = org.partition(': ')  # results in: ['first_part', 'delim', 'latter part']
            if split_org[2] == '':  # Occurs when the delimiter isn't present in the string.
                formatted_orgs.append(split_org[0])  # Returns the original string
            else:
                formatted_orgs.append(split_org[2])
        if not formatted_orgs:
            final_orgs = ''
        else:
            final_orgs = ' ({})'.format(', '.join(formatted_orgs))

        edx_formatted_title = '{} - via edX.org'.format(content_metadata_item.get('title'))
        return '{}{}'.format(
            edx_formatted_title,
            final_orgs
        )

    def transform_description(self, content_metadata_item):
        """
        Return the course description and enrollment url as Moodle' syllabus body attribute.
        This will display in the Syllabus tab in Moodle.
        """
        enrollment_url = content_metadata_item.get('enrollment_url', None)
        base_description = '<a href={enrollment_url} target="_blank">Go to edX course page</a><br />'.format(
            enrollment_url=enrollment_url)
        full_description = content_metadata_item.get('full_description') or None
        short_description = content_metadata_item.get('short_description') or None
        if full_description and len(full_description + enrollment_url) <= self.LONG_STRING_LIMIT:
            description = "{base_description}{full_description}".format(
                base_description=base_description,
                full_description=full_description
            )
        elif short_description and len(short_description + enrollment_url) <= self.LONG_STRING_LIMIT:
            short_description = content_metadata_item.get('short_description')
            description = "{base_description}{short_description}".format(
                base_description=base_description, short_description=short_description
            )
        else:
            description = "{base_description}{title}".format(
                base_description=base_description,
                title=content_metadata_item.get('title', '')
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
            return int(parse(start_date).replace(tzinfo=timezone.utc).timestamp())
        return None

    def transform_end(self, content_metadata_item):
        """
        Converts end from ISO date string to int (required for Moodle's "enddate" field)
        """
        end_date = content_metadata_item.get('end', None)
        if end_date:
            return int(parse(end_date).replace(tzinfo=timezone.utc).timestamp())
        return None
