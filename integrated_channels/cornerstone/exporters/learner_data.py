# -*- coding: utf-8 -*-
"""
Learner data exporter for Enterprise Integrated Channel Cornerstone.
"""

from logging import getLogger

from django.apps import apps

from enterprise.api_client.discovery import get_course_catalog_api_service_client
from integrated_channels.integrated_channel.exporters.learner_data import LearnerExporter

LOGGER = getLogger(__name__)


class CornerstoneLearnerExporter(LearnerExporter):
    """
    Class to provide a Cornerstone learner data transmission audit prepared for serialization.
    """

    def get_learner_data_records(self, enterprise_enrollment, completed_date=None, grade=None, is_passing=False):
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

        course_catalog_client = get_course_catalog_api_service_client(
            site=enterprise_enrollment.enterprise_customer_user.enterprise_customer.site
        )
        try:
            csod_learner_data_transmission = CornerstoneLearnerDataTransmissionAudit.objects.get(
                user_id=enterprise_enrollment.enterprise_customer_user.user.id,
                course_id=course_catalog_client.get_course_id(enterprise_enrollment.course_id),
            )
            csod_learner_data_transmission.enterprise_course_enrollment_id = enterprise_enrollment.id
            csod_learner_data_transmission.grade = grade
            csod_learner_data_transmission.course_completed = course_completed
            csod_learner_data_transmission.completed_timestamp = completed_date
            return [
                csod_learner_data_transmission
            ]
        except CornerstoneLearnerDataTransmissionAudit.DoesNotExist:
            LOGGER.info(
                'No learner data was sent for user [%s] because Cornerstone user ID could not be found '
                'for customer [%s]',
                enterprise_enrollment.enterprise_customer_user.username,
                enterprise_enrollment.enterprise_customer_user.enterprise_customer.name
            )
