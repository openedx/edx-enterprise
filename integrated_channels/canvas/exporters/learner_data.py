# -*- coding: utf-8 -*-
"""
Learner data exporter for Enterprise Integrated Channel Canvas.
"""

from datetime import datetime
from logging import getLogger

from django.apps import apps

from enterprise.api_client.discovery import get_course_catalog_api_service_client
from integrated_channels.integrated_channel.exporters.learner_data import LearnerExporter

LOGGER = getLogger(__name__)


class CanvasLearnerExporter(LearnerExporter):
    """
    Class to provide a Canvas learner data transmission audit prepared for serialization.
    """
    def get_learner_data_records(
            self,
            enterprise_enrollment,
            completed_date=None,
            is_passing=False,
            **kwargs
    ):  # pylint: disable=arguments-differ,unused-argument
        """
        Return a CanvasLearnerDataTransmissionAudit with the given enrollment and course completion data.

        If completed_date is None, then course completion has not been met.

        If no remote ID can be found, return None.
        """
        enterprise_customer_user = enterprise_enrollment.enterprise_customer_user
        if enterprise_customer_user.user_email is None:
            LOGGER.debug(
                'No learner data was sent for user [%s] because a Canvas user ID could not be found.',
                enterprise_customer_user.username
            )
            return None
        percent_grade = kwargs.get('grade_percent', None)
        completed_timestamp = completed_date.strftime("%F") if isinstance(completed_date, datetime) else None

        course_catalog_client = get_course_catalog_api_service_client(
            site=enterprise_customer_user.enterprise_customer.site
        )

        CanvasLearnerDataTransmissionAudit = apps.get_model(  # pylint: disable=invalid-name
            'canvas',
            'CanvasLearnerDataTransmissionAudit'
        )
        # We return two records here, one with the course key and one with the course run id, to account for
        # uncertainty about the type of content (course vs. course run) that was sent to the integrated channel.
        return [
            CanvasLearnerDataTransmissionAudit(
                enterprise_course_enrollment_id=enterprise_enrollment.id,
                canvas_user_email=enterprise_customer_user.user_email,
                course_id=course_catalog_client.get_course_id(enterprise_enrollment.course_id),
                course_completed=completed_date is not None and is_passing,
                grade=percent_grade,
                completed_timestamp=completed_timestamp,
            ),
        ]

    def get_learner_assessment_data_records(
            self,
            enterprise_enrollment,
            assessment_grade_data,
    ):
        """
        Return a CanvasLearnerAssessmentDataTransmissionAudit with the given enrollment and assessment level data.

        If there is no subsection grade then something has gone horribly wrong and it is recommended to look at the
        return value of platform's gradebook view.

        If no remote ID (enterprise user's email) can be found, return None as that is used to match the learner with
        their Canvas account.

        Parameters:
        -----------
            enterprise_enrollment (EnterpriseCourseEnrollment object):  Django model containing the enterprise
                customer, course ID, and enrollment source.
            assessment_grade_data (Dict): learner data retrieved from platform's gradebook api.
        """
        enterprise_customer_user = enterprise_enrollment.enterprise_customer_user
        if enterprise_customer_user.user_email is None:
            # We need an email to find the user on Canvas.
            LOGGER.debug(
                'No learner data was sent for user [%s] because a Canvas user ID could not be found.',
                enterprise_enrollment.enterprise_customer_user.username
            )
            return None

        CanvasLearnerAssessmentDataTransmissionAudit = apps.get_model(  # pylint: disable=invalid-name
            'canvas',
            'CanvasLearnerAssessmentDataTransmissionAudit'
        )

        user_subsection_audits = []
        # Create an audit for each of the subsections exported.
        for subsection_name, subsection_data in assessment_grade_data.items():
            subsection_percent_grade = subsection_data.get('grade')
            subsection_id = subsection_data.get('subsection_id')
            # Sanity check for a grade to report
            if not subsection_percent_grade or not subsection_id:
                continue

            course_catalog_client = get_course_catalog_api_service_client(
                site=enterprise_customer_user.enterprise_customer.site
            )

            transmission_audit = CanvasLearnerAssessmentDataTransmissionAudit(
                enterprise_course_enrollment_id=enterprise_enrollment.id,
                canvas_user_email=enterprise_customer_user.user_email,
                course_id=course_catalog_client.get_course_id(enterprise_enrollment.course_id),
                subsection_id=subsection_id,
                grade=subsection_percent_grade,
                grade_point_score=subsection_data.get('grade_point_score'),
                grade_points_possible=subsection_data.get('grade_points_possible'),
                subsection_name=subsection_name
            )
            user_subsection_audits.append(transmission_audit)

        return user_subsection_audits
