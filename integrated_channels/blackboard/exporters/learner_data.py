# -*- coding: utf-8 -*-
"""
Learner data exporter for Enterprise Integrated Channel Blackboard.
"""

from logging import getLogger

from django.apps import apps

from integrated_channels.catalog_service_utils import get_course_id_for_enrollment
from integrated_channels.integrated_channel.exporters.learner_data import LearnerExporter
from integrated_channels.utils import generate_formatted_log, parse_datetime_to_epoch_millis

LOGGER = getLogger(__name__)


class BlackboardLearnerExporter(LearnerExporter):
    """
    Class to provide a Blackboard learner data transmission audit prepared for serialization.
    """

    def get_learner_data_records(
            self,
            enterprise_enrollment,
            completed_date=None,
            course_completed=False,
            **kwargs
    ):  # pylint: disable=arguments-differ
        """
        Return a BlackboardLearnerDataTransmissionAudit with the given enrollment and course completion data.
        If no remote ID can be found, return None.
        """
        enterprise_customer_user = enterprise_enrollment.enterprise_customer_user
        if enterprise_customer_user.user_email is None:
            LOGGER.debug(generate_formatted_log(
                self.enterprise_configuration.channel_code(),
                enterprise_customer_user.enterprise_customer.uuid,
                enterprise_customer_user.user_id,
                None,
                ('get_learner_data_records finished. No learner data was sent for this LMS User Id because '
                 'Blackboard User ID not found for [{name}]'.format(
                     name=enterprise_customer_user.enterprise_customer.name
                 ))))
            return None
        percent_grade = kwargs.get('grade_percent', None)
        completed_timestamp = None
        if completed_date is not None:
            completed_timestamp = parse_datetime_to_epoch_millis(completed_date)

        BlackboardLearnerDataTransmissionAudit = apps.get_model(
            'blackboard',
            'BlackboardLearnerDataTransmissionAudit'
        )

        return [
            BlackboardLearnerDataTransmissionAudit(
                enterprise_course_enrollment_id=enterprise_enrollment.id,
                blackboard_user_email=enterprise_customer_user.user_email,
                course_id=get_course_id_for_enrollment(enterprise_enrollment),
                course_completed=course_completed,
                grade=percent_grade,
                completed_timestamp=completed_timestamp,
            )
        ]

    def get_learner_assessment_data_records(
            self,
            enterprise_enrollment,
            assessment_grade_data,
    ):
        """
        Return a blackboardLearnerDataTransmissionAudit with the given enrollment and assessment level data.
        If there is no subsection grade then something has gone horribly wrong and it is recommended to look at the
        return value of platform's gradebook view.
        If no remote ID (enterprise user's email) can be found, return None as that is used to match the learner with
        their blackboard account.

        Parameters:
        -----------
            enterprise_enrollment (EnterpriseCourseEnrollment object):  Django model containing the enterprise
                customer, course ID, and enrollment source.
            assessment_grade_data (Dict): learner data retrieved from platform's gradebook api.
        """
        if enterprise_enrollment.enterprise_customer_user.user_email is None:
            # We need an email to find the user on blackboard.
            LOGGER.debug(generate_formatted_log(
                self.enterprise_configuration.channel_code(),
                enterprise_enrollment.enterprise_customer_user.enterprise_customer.uuid,
                enterprise_enrollment.enterprise_customer_user.user_id,
                None,
                ('get_learner_assessment_data_records finished. No learner data was sent for this LMS User Id because'
                 ' Blackboard User ID not found for [{name}]'.format(
                     name=enterprise_enrollment.enterprise_customer_user.enterprise_customer.name
                 ))))
            return None

        blackboardLearnerAssessmentDataTransmissionAudit = apps.get_model(
            'blackboard',
            'blackboardLearnerAssessmentDataTransmissionAudit'
        )

        user_subsection_audits = []
        # Create an audit for each of the subsections exported.
        for subsection_name, subsection_data in assessment_grade_data.items():
            subsection_percent_grade = subsection_data.get('grade')
            subsection_id = subsection_data.get('subsection_id')
            # Sanity check for a grade to report
            if not subsection_percent_grade or not subsection_id:
                continue

            transmission_audit = blackboardLearnerAssessmentDataTransmissionAudit(
                enterprise_course_enrollment_id=enterprise_enrollment.id,
                blackboard_user_email=enterprise_enrollment.enterprise_customer_user.user_email,
                course_id=get_course_id_for_enrollment(enterprise_enrollment),
                subsection_id=subsection_id,
                grade=subsection_percent_grade,
                grade_point_score=subsection_data.get('grade_point_score'),
                grade_points_possible=subsection_data.get('grade_points_possible'),
                subsection_name=subsection_name
            )
            user_subsection_audits.append(transmission_audit)

        return user_subsection_audits
