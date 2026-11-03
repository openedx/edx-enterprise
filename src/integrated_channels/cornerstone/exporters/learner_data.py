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
            content_title=None,
            progress_status=None,
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
            # get the proper internal representation of the course key
            course_id = get_course_id_for_enrollment(enterprise_enrollment)
            # because CornerstoneLearnerDataTransmissionAudit records are created with a click-through
            # the internal edX course_id is always used on the CornerstoneLearnerDataTransmissionAudit records
            # rather than the external_course_id mapped via CornerstoneCourseKey
            csod_learner_data_transmission = CornerstoneLearnerDataTransmissionAudit.objects.get(
                user_id=enterprise_enrollment.enterprise_customer_user.user.id,
                course_id=course_id,
                plugin_configuration_id=self.enterprise_configuration.id,
                enterprise_customer_uuid=self.enterprise_configuration.enterprise_customer.uuid,
            )
            csod_learner_data_transmission.enterprise_course_enrollment_id = enterprise_enrollment.id
            csod_learner_data_transmission.grade = grade
            csod_learner_data_transmission.course_completed = course_completed
            csod_learner_data_transmission.completed_timestamp = completed_date
            csod_learner_data_transmission.content_title = content_title
            csod_learner_data_transmission.progress_status = progress_status

            # Used for api error reporting
            csod_learner_data_transmission.user_email = enterprise_enrollment.enterprise_customer_user.user_email

            enterprise_customer = enterprise_enrollment.enterprise_customer_user.enterprise_customer
            csod_learner_data_transmission.enterprise_customer_uuid = enterprise_customer.uuid
            csod_learner_data_transmission.plugin_configuration_id = self.enterprise_configuration.id
            return [
                csod_learner_data_transmission
            ]
        except CornerstoneLearnerDataTransmissionAudit.DoesNotExist:
            LOGGER.info(generate_formatted_log(
                self.enterprise_configuration.channel_code(),
                enterprise_enrollment.enterprise_customer_user.enterprise_customer.uuid,
                enterprise_enrollment.enterprise_customer_user.user_id,
                enterprise_enrollment.course_id,
                (
                    'get_learner_data_records finished. No learner data was sent for this LMS User Id {user_id} '
                    'because Cornerstone User ID not found'.format(
                        user_id=enterprise_enrollment.enterprise_customer_user.user_id
                    )
                )
            ))
            return None
