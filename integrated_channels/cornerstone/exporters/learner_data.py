# -*- coding: utf-8 -*-
"""
Learner data exporter for Enterprise Integrated Channel Cornerstone.
"""

from logging import getLogger

from django.apps import apps

from integrated_channels.catalog_service_utils import get_course_id_for_enrollment
from integrated_channels.cornerstone.utils import get_or_create_key_pair
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
            course_completed=False,
            **kwargs,
    ):  # pylint: disable=arguments-differ
        """
        Return a CornerstoneLearnerDataTransmissionAudit with the given enrollment and course completion data.

        CornerstoneLearnerDataTransmissionAudit object should exit already if not then return None.
        """

        CornerstoneLearnerDataTransmissionAudit = apps.get_model(
            'cornerstone',
            'CornerstoneLearnerDataTransmissionAudit'
        )

        try:
            course_id = get_course_id_for_enrollment(enterprise_enrollment)
            key_mapping = get_or_create_key_pair(course_id)
            csod_learner_data_transmission = CornerstoneLearnerDataTransmissionAudit.objects.get(
                user_id=enterprise_enrollment.enterprise_customer_user.user.id,
                course_id=key_mapping.external_course_id,
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
                self.enterprise_configuration.channel_code(),
                enterprise_enrollment.enterprise_customer_user.enterprise_customer.uuid,
                enterprise_enrollment.enterprise_customer_user.user_id,
                None,
                ('get_learner_data_records finished. No learner data was sent for this LMS User Id because '
                 'Cornerstone User ID not found for [{name}]'.format(
                     name=enterprise_enrollment.enterprise_customer_user.enterprise_customer.name
                 ))))
            return None
