# -*- coding: utf-8 -*-
"""
Learner data exporter for Enterprise Integrated Channel Cornerstone.
"""

from logging import getLogger

from django.apps import apps

from integrated_channels.catalog_service_utils import get_course_id_for_enrollment
from integrated_channels.integrated_channel.exporters.learner_data import LearnerExporter
from integrated_channels.utils import generate_formatted_log

LOGGER = getLogger(__name__)


class CornerstoneLearnerExporter(LearnerExporter):
    """
    Class to provide a Cornerstone learner data transmission audit prepared for serialization.
    """

    def get_learner_data_records(
            self,
            enterprise_enrollment,
            completed_date=None,
            grade=None,
            is_passing=False,
            grade_percent=None
    ):
        """
        Return a CornerstoneLearnerDataTransmissionAudit with the given enrollment and course completion data.

        If completed_date is None, then course completion has not been met.

        CornerstoneLearnerDataTransmissionAudit object should exit already if not then return None.
        """
        course_completed = False
        if completed_date is not None:
            course_completed = True

        CornerstoneLearnerDataTransmissionAudit = apps.get_model(  # pylint: disable=invalid-name
            'cornerstone',
            'CornerstoneLearnerDataTransmissionAudit'
        )

        try:
            csod_learner_data_transmission = CornerstoneLearnerDataTransmissionAudit.objects.get(
                user_id=enterprise_enrollment.enterprise_customer_user.user.id,
                course_id=get_course_id_for_enrollment(enterprise_enrollment),
            )
            csod_learner_data_transmission.enterprise_course_enrollment_id = enterprise_enrollment.id
            csod_learner_data_transmission.grade = grade
            csod_learner_data_transmission.course_completed = course_completed
            csod_learner_data_transmission.completed_timestamp = completed_date
            return [
                csod_learner_data_transmission
            ]
        except CornerstoneLearnerDataTransmissionAudit.DoesNotExist:
            LOGGER.info(generate_formatted_log(
                'cornerstone',
                enterprise_enrollment.enterprise_customer_user.enterprise_customer.uuid,
                enterprise_enrollment.enterprise_customer_user.user_id,
                None,
                ('get_learner_data_records finished. No learner data was sent for this LMS User Id because '
                 'Cornerstone User ID not found for [{name}]'.format(
                     name=enterprise_enrollment.enterprise_customer_user.enterprise_customer.name
                 ))))
            return None
