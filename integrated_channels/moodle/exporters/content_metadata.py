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
        'fullname': 'fullname',
        'shortname': 'shortname',
        'idnumber': 'key',
        'startdate': 'start',
        'enddate': 'end',
        'categoryid': 'categoryid',
        'format': 'format',
        'announcement': 'announcement',
    }

# default url length = 8000 bytes / max char size of 4 bytes = 2000 char limit
# subtracted arbitrary char buffer for template HTML, token, and other query params we send.
    LONG_STRING_LIMIT = 1500
    SKIP_KEY_IF_NONE = True

    ANNOUNCEMENT_TEMPLATE = '<div><div style="display: inline-block">' \
        '<h1 style="font-size:xxx-large; margin-bottom:0; margin-top:0">{title}</h1>' \
        '<a href={enrollment_url} style="font-size:150%">Go to edX course page</a><br/><hr/>' \
        '</div><br/><img src={image_url} style="max-width:400px" width="30%" border="40px"/>' \
        '<br/><br/><br/><p style="width:60%;">{description}</p></div>'

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

    def transform_fullname(self, content_metadata_item):
        """
        Returns the course title with all organizations (partners) appended in parantheses
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

        return '{}{}'.format(
            content_metadata_item.get('title'),
            final_orgs
        )

    def transform_categoryid(self, content_metadata_item):  # pylint: disable=unused-argument
        """
        Returns the Moodle category id configured in the model.
        ID 1 is Miscellaneous and is the default/basic category.
        """
        return self.enterprise_configuration.category_id or 1

    def transform_format(self, content_metadata_item):  # pylint: disable=unused-argument
        """
        Return Moodle course format specific for displaying Announcement posts.
        """
        return "singleactivity"

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

    def transform_announcement(self, content_metadata_item):
        """
        Formats a post in a course's Announcement forum with
        edX's course summary and enrollment link
        """
        full_description = content_metadata_item.get('full_description') or None
        short_description = content_metadata_item.get('short_description') or None

        if full_description and len(full_description) <= self.LONG_STRING_LIMIT:
            description = full_description
        else:
            description = short_description

        return self.ANNOUNCEMENT_TEMPLATE.format(
            title=content_metadata_item.get('title', None),
            enrollment_url=content_metadata_item.get('enrollment_url', None),
            image_url=content_metadata_item.get('image_url', None),
            description=description
        )
