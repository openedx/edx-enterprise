"""
Learner data exporter for Enterprise Integrated Channel Moodle.
"""

from logging import getLogger

from django.apps import apps

from integrated_channels.catalog_service_utils import get_course_id_for_enrollment
from integrated_channels.integrated_channel.exporters.learner_data import LearnerExporter
from integrated_channels.utils import generate_formatted_log, parse_datetime_to_epoch_millis

LOGGER = getLogger(__name__)


class MoodleLearnerExporter(LearnerExporter):
    """
    Class to provide a Moodle learner data transmission audit prepared for serialization.
    """

    def get_learner_data_records(
            self,
            enterprise_enrollment,
            completed_date=None,
            content_title=None,
            progress_status=None,
            course_completed=False,
            **kwargs
    ):  # pylint: disable=arguments-differ
        """
        Return a MoodleLearnerDataTransmissionAudit with the given enrollment and course completion data.
        If no remote ID can be found, return None.
        """
        enterprise_customer_user = enterprise_enrollment.enterprise_customer_user
        moodle_completed_timestamp = None
        if completed_date is not None:
            moodle_completed_timestamp = parse_datetime_to_epoch_millis(completed_date)

        if enterprise_customer_user.user_email is None:
            LOGGER.debug(generate_formatted_log(
                'moodle',
                enterprise_customer_user.enterprise_customer.uuid,
                enterprise_customer_user.user_id,
                None,
                ('get_learner_data_records finished. No learner data was sent for this LMS User Id because '
                 'Moodle User ID not found for [{name}]'.format(
                     name=enterprise_customer_user.enterprise_customer.name
                 ))))
            return None

        MoodleLearnerDataTransmissionAudit = apps.get_model(
            'moodle',
            'MoodleLearnerDataTransmissionAudit'
        )

        percent_grade = kwargs.get('grade_percent', None)
        course_id = get_course_id_for_enrollment(enterprise_enrollment)
        # We only want to send one record per enrollment and course, so we check if one exists first.
        learner_transmission_record = MoodleLearnerDataTransmissionAudit.objects.filter(
            enterprise_course_enrollment_id=enterprise_enrollment.id,
            course_id=course_id,
        ).first()
        if learner_transmission_record is None:
            learner_transmission_record = MoodleLearnerDataTransmissionAudit(
                enterprise_course_enrollment_id=enterprise_enrollment.id,
                moodle_user_email=enterprise_customer_user.user_email,
                user_email=enterprise_customer_user.user_email,
                course_id=get_course_id_for_enrollment(enterprise_enrollment),
                course_completed=course_completed,
                grade=percent_grade,
                completed_timestamp=completed_date,
                content_title=content_title,
                progress_status=progress_status,
                moodle_completed_timestamp=moodle_completed_timestamp,
                enterprise_customer_uuid=enterprise_customer_user.enterprise_customer.uuid,
                plugin_configuration_id=self.enterprise_configuration.id,
            )
        # We return one record here, with the course key, that was sent to the integrated channel.
        # TODO: this shouldn't be necessary anymore and eventually phased out as part of tech debt
        return [learner_transmission_record]
