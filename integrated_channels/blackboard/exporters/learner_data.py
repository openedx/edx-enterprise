# -*- coding: utf-8 -*-
"""
Learner data exporter for Enterprise Integrated Channel Blackboard.
"""

from logging import getLogger

from django.apps import apps

from enterprise.api_client.discovery import get_course_catalog_api_service_client
from integrated_channels.integrated_channel.exporters.learner_data import LearnerExporter
from integrated_channels.utils import parse_datetime_to_epoch_millis

LOGGER = getLogger(__name__)


class BlackboardLearnerExporter(LearnerExporter):
    """
    Class to provide a Blackboard learner data transmission audit prepared for serialization.
    """

    def get_learner_data_records(
            self,
            enterprise_enrollment,
            completed_date=None,
            is_passing=False,
            **kwargs
    ):  # pylint: disable=arguments-differ,unused-argument
        """
        Return a BlackboardLearnerDataTransmissionAudit with the given enrollment and course completion data.
        If completed_date is None, then course completion has not been met.
        If no remote ID can be found, return None.
        """
        enterprise_customer = enterprise_enrollment.enterprise_customer_user
        completed_timestamp = None
        if completed_date is not None:
            completed_timestamp = parse_datetime_to_epoch_millis(completed_date)

        if enterprise_customer.user_email is None:
            LOGGER.debug(
                'No learner data was sent for user [%s] because a Blackboard user ID could not be found.',
                enterprise_customer.username
            )
            return None

        BlackboardLearnerDataTransmissionAudit = apps.get_model(  # pylint: disable=invalid-name
            'blackboard',
            'BlackboardLearnerDataTransmissionAudit'
        )

        course_catalog_client = get_course_catalog_api_service_client(
            site=enterprise_customer.enterprise_customer.site
        )

        percent_grade = kwargs.get('grade_percent', None)

        return [
            BlackboardLearnerDataTransmissionAudit(
                enterprise_course_enrollment_id=enterprise_enrollment.id,
                blackboard_user_email=enterprise_customer.user_email,
                course_id=course_catalog_client.get_course_id(enterprise_enrollment.course_id),
                course_completed=completed_date is not None and is_passing,
                grade=percent_grade,
                completed_timestamp=completed_timestamp,
            ),
            BlackboardLearnerDataTransmissionAudit(
                enterprise_course_enrollment_id=enterprise_enrollment.id,
                blackboard_user_email=enterprise_customer.user_email,
                course_id=enterprise_enrollment.course_id,
                course_completed=completed_date is not None and is_passing,
                grade=percent_grade,
                completed_timestamp=completed_timestamp,
            )
        ]
