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
        if enterprise_enrollment.enterprise_customer_user.user_email is None:
            LOGGER.debug(
                'No learner data was sent for user [%s] because a Canvas user ID could not be found.',
                enterprise_enrollment.enterprise_customer_user.username
            )
            return None
        percent_grade = kwargs.get('grade_percent', None)
        completed_timestamp = completed_date.strftime("%F") if isinstance(completed_date, datetime) else None

        CanvasLearnerDataTransmissionAudit = apps.get_model(  # pylint: disable=invalid-name
            'canvas',
            'CanvasLearnerDataTransmissionAudit'
        )
        # We return two records here, one with the course key and one with the course run id, to account for
        # uncertainty about the type of content (course vs. course run) that was sent to the integrated channel.
        course_catalog_client = get_course_catalog_api_service_client(
            site=enterprise_enrollment.enterprise_customer_user.enterprise_customer.site
        )
        return [
            CanvasLearnerDataTransmissionAudit(
                enterprise_course_enrollment_id=enterprise_enrollment.id,
                canvas_user_email=enterprise_enrollment.enterprise_customer_user.user_email,
                course_id=course_catalog_client.get_course_id(enterprise_enrollment.course_id),
                course_completed=completed_date is not None and is_passing,
                completed_timestamp=completed_timestamp,
                grade=percent_grade
            ),
            CanvasLearnerDataTransmissionAudit(
                enterprise_course_enrollment_id=enterprise_enrollment.id,
                canvas_user_email=enterprise_enrollment.enterprise_customer_user.user_email,
                course_id=enterprise_enrollment.course_id,
                course_completed=completed_date is not None and is_passing,
                completed_timestamp=completed_timestamp,
                grade=percent_grade
            )
        ]
