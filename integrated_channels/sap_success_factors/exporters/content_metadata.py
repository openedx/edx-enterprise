"""
Content metadata exporter for SAP SuccessFactors.
"""

from logging import getLogger

from django.utils.translation import gettext_lazy as _

from enterprise.constants import IC_DELETE_ACTION
from enterprise.utils import (
    get_advertised_course_run,
    get_closest_course_run,
    get_duration_of_course_or_courserun,
    is_course_run_active,
    is_course_run_available_for_enrollment,
    parse_lms_api_datetime,
)
from enterprise.views import CourseEnrollmentView
from integrated_channels.integrated_channel.exporters.content_metadata import ContentMetadataExporter
from integrated_channels.sap_success_factors.exporters.utils import transform_language_code
from integrated_channels.utils import (
    UNIX_MAX_DATE_STRING,
    UNIX_MIN_DATE_STRING,
    current_time_is_in_interval,
    get_image_url,
    parse_datetime_to_epoch_millis,
)

LOGGER = getLogger(__name__)


class SapSuccessFactorsContentMetadataExporter(ContentMetadataExporter):
    """
    SAP SuccessFactors implementation of ContentMetadataExporter.
    """

    DATA_TRANSFORM_MAPPING = {
        'courseID': 'key',
        'providerID': 'provider_id',
        'status': 'status',
        'title': 'title',
        'description': 'description',
        'thumbnailURI': 'image',
        'content': 'launch_points',
        'revisionNumber': 'revision_number',
        'schedule': 'schedule',
        'price': 'price',
    }

    def _apply_delete_transformation(self, metadata):
        """
        Specific transformations required for "deleting" a course on a SAP external service.
        """
        # Applying the metadata payload update to "delete" the course on SAP instances
        metadata['status'] = 'INACTIVE'

        # Sanity check as we've seen issues with schedule structure
        metadata_schedule = metadata.get('schedule')
        if metadata_schedule:
            schedule = metadata_schedule[0]
            if not schedule.get('startDate') or not schedule.get('endDate'):
                metadata['schedule'] = []
        return metadata

    def transform_provider_id(self, content_metadata_item):  # pylint: disable=unused-argument
        """
        Return the provider ID from the integrated channel configuration.
        """
        return self.enterprise_configuration.provider_id

    def transform_for_action_status(self, _content_metadata_item, action):
        """
        Return the status of the content item.
        """
        # lets not overwrite something we've already tried to set INACTIVE
        if action == IC_DELETE_ACTION:
            return 'INACTIVE'
        else:
            return 'ACTIVE'

    def transform_title(self, content_metadata_item):
        """
        Return the title of the content item.
        """
        title_with_locales = []

        for locale in self.enterprise_configuration.get_locales():
            title_with_locales.append({
                'locale': locale,
                'value': content_metadata_item.get('title', '')
            })

        return title_with_locales

    def transform_description(self, content_metadata_item):
        """
        Return the description of the content item. Also include the course pacing, and start and end dates.
        """
        description_with_locales = []

        description = (
            content_metadata_item.get('full_description') or
            content_metadata_item.get('short_description') or
            content_metadata_item.get('title', '')
        )

        course_run = get_advertised_course_run(content_metadata_item)

        if not course_run:
            course_runs = content_metadata_item.get('course_runs')
            if course_runs:
                course_run = get_closest_course_run(course_runs)

        if course_run:
            # Include the course run start and end dates
            date_str = self._get_course_run_start_end_str(course_run)
            if date_str:
                description = date_str + description

            # Include the course pacing
            course_pacing = CourseEnrollmentView.PACING_FORMAT.get(course_run['pacing_type'], '')
            if course_pacing:
                pacing_desc = 'Pacing: {pacing_type}. '.format(
                    pacing_type=course_pacing
                )
                description = pacing_desc + description

        for locale in self.enterprise_configuration.get_locales():
            description_with_locales.append({
                'locale': locale,
                'value': description
            })

        return description_with_locales

    def transform_image(self, content_metadata_item):
        """
        Return the image URI of the content item.
        """
        return get_image_url(content_metadata_item)

    def transform_launch_points(self, content_metadata_item):
        """
        Return the content metadata item launch points.

        SAPSF allows you to transmit an array of content launch points which
        are meant to represent sections of a content item which a learner can
        launch into from SAPSF. Currently, we only provide a single launch
        point for a content item.
        """
        return [{
            'providerID': self.enterprise_configuration.provider_id,
            'launchURL': content_metadata_item['enrollment_url'],
            'contentTitle': content_metadata_item['title'],
            'contentID': self._get_content_id(content_metadata_item),
            'launchType': 3,  # This tells SAPSF to launch the course in a new browser window.
            'mobileEnabled': True,  # Always return True per ENT-1401
            'mobileLaunchURL': content_metadata_item['enrollment_url'],
        }]

    def transform_revision_number(self, content_metadata_item):  # pylint: disable=unused-argument
        """
        Return the revision number.
        """
        return 1

    def transform_schedule(self, content_metadata_item):
        """
        Return the schedule of the content item.
        """
        duration, start, end = get_duration_of_course_or_courserun(content_metadata_item)

        # SAP will throw errors if we try to send an empty start or end date
        if (not start or not end):
            return []

        return [{
            'startDate': parse_datetime_to_epoch_millis(start) if start else '',
            'endDate': parse_datetime_to_epoch_millis(end) if end else '',
            'active': current_time_is_in_interval(start, end) if start else False,
            'duration': f"{duration} days",
        }]

    def transform_price(self, content_metadata_item):
        """
        Return the current course run's price.
        """
        price = 0.0

        if self.enterprise_configuration.show_course_price:
            advertised_course_run = get_advertised_course_run(content_metadata_item)
            if advertised_course_run and 'first_enrollable_paid_seat_price' in advertised_course_run:
                price = advertised_course_run.get('first_enrollable_paid_seat_price') or 0.0
            else:
                for course_run in content_metadata_item.get('course_runs', []):
                    if 'first_enrollable_paid_seat_price' in course_run and is_course_run_active(course_run):
                        price = course_run.get('first_enrollable_paid_seat_price') or 0.0
                        break

        return [
            {
                "currency": "USD",
                "value": price
            }
        ]

    def transform_courserun_title(self, content_metadata_item):
        """
        Return the title of the courserun content item.
        """
        title = content_metadata_item.get('title') or ''
        course_run_start = content_metadata_item.get('start')

        if course_run_start:
            if is_course_run_available_for_enrollment(content_metadata_item):
                title += ' ({starts}: {:%B %Y})'.format(
                    parse_lms_api_datetime(course_run_start),
                    starts=_('Starts')
                )
            else:
                title += ' ({:%B %Y} - {enrollment_closed})'.format(
                    parse_lms_api_datetime(course_run_start),
                    enrollment_closed=_('Enrollment Closed')
                )

        title_with_locales = []
        content_metadata_language_code = transform_language_code(content_metadata_item.get('content_language', ''))
        for locale in self.enterprise_configuration.get_locales(default_locale=content_metadata_language_code):
            title_with_locales.append({
                'locale': locale,
                'value': title
            })

        return title_with_locales

    def transform_courserun_description(self, content_metadata_item):
        """
        Return the description of the courserun content item.
        """
        description_with_locales = []
        content_metadata_language_code = transform_language_code(content_metadata_item.get('content_language', ''))
        for locale in self.enterprise_configuration.get_locales(default_locale=content_metadata_language_code):
            description_with_locales.append({
                'locale': locale,
                'value': (
                    content_metadata_item['full_description'] or
                    content_metadata_item['short_description'] or
                    content_metadata_item['title'] or
                    ''
                )
            })

        return description_with_locales

    def transform_courserun_schedule(self, content_metadata_item):
        """
        Return the schedule of the courserun content item.
        """
        start = content_metadata_item.get('start') or UNIX_MIN_DATE_STRING
        end = content_metadata_item.get('end') or UNIX_MAX_DATE_STRING
        return [{
            'startDate': parse_datetime_to_epoch_millis(start),
            'endDate': parse_datetime_to_epoch_millis(end),
            'active': current_time_is_in_interval(start, end)
        }]

    def transform_program_key(self, content_metadata_item):
        """
        Return the identifier of the program content item.
        """
        return content_metadata_item['uuid']

    def _get_content_id(self, content_metadata_item):
        """
        Return the id for the given content_metadata_item, `uuid` for programs or `key` for other content
        """
        content_id = content_metadata_item.get('key', '')
        if content_metadata_item['content_type'] == 'program':
            content_id = content_metadata_item.get('uuid', '')
        return content_id

    def _get_course_run_start_end_str(self, course_run):
        """
        Get the course run start and end as a descriptive string. Also include a note if enrollment is closed.
        """
        course_run_start = course_run.get('start')
        course_run_end = course_run.get('end')
        date_str = ''

        if course_run_start:
            date_str += '{starts}: {:%B %Y}'.format(
                parse_lms_api_datetime(course_run_start),
                starts=_('Starts')
            )

        if course_run_end:
            if date_str:
                date_str += ', '

            date_str += '{ends}: {:%B %Y}. '.format(
                parse_lms_api_datetime(course_run_end),
                ends=_('Ends')
            )
        else:
            if date_str:
                date_str += '. '

        if not is_course_run_available_for_enrollment(course_run):
            date_str += 'Enrollment is closed. '

        return date_str
