# -*- coding: utf-8 -*-
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
            is_passing=False,
            **kwargs
    ):  # pylint: disable=arguments-differ,unused-argument
        """
        Return a MoodleLearnerDataTransmissionAudit with the given enrollment and course completion data.
        If completed_date is None, then course completion has not been met.
        If no remote ID can be found, return None.
        """
        enterprise_learner = enterprise_enrollment.enterprise_customer_user
        completed_timestamp = None
        if completed_date is not None:
            completed_timestamp = parse_datetime_to_epoch_millis(completed_date)

        if enterprise_learner.user_email is None:
            LOGGER.debug(generate_formatted_log(
                'moodle',
                enterprise_learner.enterprise_customer.uuid,
                enterprise_learner.user_id,
                None,
                ('get_learner_data_records finished. No learner data was sent for this LMS User Id because '
                 'Moodle User ID not found for [{name}]'.format(
                     name=enterprise_enrollment.enterprise_customer_user.enterprise_customer.name
                 ))))
            return None

        MoodleLearnerDataTransmissionAudit = apps.get_model(  # pylint: disable=invalid-name
            'moodle',
            'MoodleLearnerDataTransmissionAudit'
        )

        percent_grade = kwargs.get('grade_percent', None)

        return [
            MoodleLearnerDataTransmissionAudit(
                enterprise_course_enrollment_id=enterprise_enrollment.id,
                moodle_user_email=enterprise_learner.user_email,
                course_id=get_course_id_for_enrollment(enterprise_enrollment),
                course_completed=completed_date is not None and is_passing,
                grade=percent_grade,
                completed_timestamp=completed_timestamp,
            ),
            MoodleLearnerDataTransmissionAudit(
                enterprise_course_enrollment_id=enterprise_enrollment.id,
                moodle_user_email=enterprise_learner.user_email,
                course_id=enterprise_enrollment.course_id,
                course_completed=completed_date is not None and is_passing,
                grade=percent_grade,
                completed_timestamp=completed_timestamp,
            )
        ]
