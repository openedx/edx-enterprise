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
        enterprise_customer_user = enterprise_enrollment.enterprise_customer_user
        # get the proper internal representation of the course key
        course_id = get_course_id_for_enrollment(enterprise_enrollment)
        # because CornerstoneLearnerDataTransmissionAudit records are created with a click-through
        # the internal edX course_id is always used on the CornerstoneLearnerDataTransmissionAudit records
        # rather than the external_course_id mapped via CornerstoneCourseKey
        transmission_exists = CornerstoneLearnerDataTransmissionAudit.objects.filter(
            user_id=enterprise_enrollment.enterprise_customer_user.user.id,
            course_id=course_id,
            plugin_configuration_id=self.enterprise_configuration.id,
            enterprise_customer_uuid=self.enterprise_configuration.enterprise_customer.uuid,
        ).exists()

        if transmission_exists or enterprise_customer_user.user_email is not None:
            csod_transmission_record, __ = CornerstoneLearnerDataTransmissionAudit.objects.update_or_create(
                user_id=enterprise_customer_user.user.id,
                course_id=course_id,
                plugin_configuration_id=self.enterprise_configuration.id,
                enterprise_customer_uuid=self.enterprise_configuration.enterprise_customer.uuid,
                defaults={
                    "enterprise_course_enrollment_id": enterprise_enrollment.id,
                    "grade": grade,
                    "course_completed": course_completed,
                    "completed_timestamp": completed_date,
                    "user_email": enterprise_customer_user.user_email,
                },
            )
            return [csod_transmission_record]
        else:
            LOGGER.info(
                generate_formatted_log(
                    self.enterprise_configuration.channel_code(),
                    enterprise_customer_user.enterprise_customer.uuid,
                    enterprise_customer_user.user_id,
                    enterprise_enrollment.course_id,
                    (
                        'get_learner_data_records finished. No learner data was sent for this LMS User Id because '
                        'Cornerstone User ID not found for [{name}]'.format(
                            name=enterprise_customer_user.enterprise_customer.name
                        )
                    )
                )
            )
            return None
