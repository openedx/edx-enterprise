"""
Content metadata exporter for Canvas
"""

from logging import getLogger

from integrated_channels.integrated_channel.exporters.content_metadata import ContentMetadataExporter

LOGGER = getLogger(__name__)


class BlackboardContentMetadataExporter(ContentMetadataExporter):
    """
        Blackboard implementation of ContentMetadataExporter.
        The odd choice of making enrollment_url into description with a link is best explained as:
            Blackboard does not show description by default on home page.
            However, description shows on the course search page.
            This seems to be the only place to visibly place a link for now for learners to
            find and visit the edX course page. But this can change as we explore blackboard more.
    """
    DATA_TRANSFORM_MAPPING = {
        'name': 'title',
        'externalId': 'key',
        'description': 'enrollment_url',
        'courseId': 'course_unique_key',
    }

    DESCRIPTION_TEXT_TEMPLATE = "<a href={enrollment_url}>Go to edX course page</a><br />"

    def transform_enrollment_url(self, content_metadata_item):
        """
        This will show a link to edX course on blackboard course description
        """
        enrollment_url = content_metadata_item.get('enrollment_url', None)
        url_link = self.DESCRIPTION_TEXT_TEMPLATE.format(enrollment_url=enrollment_url)
        return url_link

    def transform_course_unique_key(self, content_metadata_item):
        """
        Blackboard courseId cannot contain some chars used in edX courseIds, so using hash
        We can always look up courses by externalId whch is the same as edX courseId
        """
        return content_metadata_item.get('key').replace('+','').replace(':','').replace('/','')
