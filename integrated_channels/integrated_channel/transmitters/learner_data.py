# -*- coding: utf-8 -*-
"""
Generic learner data transmitter for integrated channels.
"""

import logging

from django.apps import apps

from integrated_channels.exceptions import ClientError
from integrated_channels.integrated_channel.client import IntegratedChannelApiClient
from integrated_channels.integrated_channel.transmitters import Transmitter
from integrated_channels.utils import is_already_transmitted

LOGGER = logging.getLogger(__name__)


class LearnerTransmitter(Transmitter):
    """
    A generic learner data transmitter.

    It may be subclassed by specific integrated channel learner data transmitters for
    each integrated channel's particular learner data transmission requirements and expectations.
    """

    def __init__(self, enterprise_configuration, client=IntegratedChannelApiClient):
        """
        By default, use the abstract integrated channel API client which raises an error when used if not subclassed.
        """
        super().__init__(
            enterprise_configuration=enterprise_configuration,
            client=client
        )

    def single_learner_assessment_grade_transmit(self, exporter, **kwargs):
        """
        Send a single assessment level grade information to the integrated channel using the client.

        Args:
            exporter: The learner assessment data exporter used to send to the integrated channel.
            kwargs: Contains integrated channel-specific information for customized transmission variables.
                - app_label: The app label of the integrated channel for whom to store learner data records for.
                - model_name: The name of the specific learner data record model to use.
                - remote_user_id: The remote ID field name of the learner on the audit model.
        """
        TransmissionAudit = apps.get_model(  # pylint: disable=invalid-name
            app_label=kwargs.get('app_label', 'integrated_channel'),
            model_name=kwargs.get('model_name', 'LearnerDataTransmissionAudit'),
        )
        kwargs.update(
            TransmissionAudit=TransmissionAudit,
        )

        # Even though we're transmitting a single learner, they can have records per assessment (multiple per course).
        for learner_data in exporter.single_assessment_level_export(**kwargs):
            serialized_payload = learner_data.serialize(enterprise_configuration=self.enterprise_configuration)
            try:
                code, body = self.client.create_assessment_reporting(
                    getattr(learner_data, kwargs.get('remote_user_id')),
                    serialized_payload
                )
            except ClientError as client_error:
                code = client_error.status_code
                body = client_error.message
                self.handle_transmission_error(learner_data, client_error)

            learner_data.status = str(code)
            learner_data.error_message = body if code >= 400 else ''

            learner_data.save()

    def assessment_level_transmit(self, exporter, **kwargs):
        """
        Send all assessment level grade information under an enterprise enrollment to the integrated channel using the
        client.

        Args:
            exporter: The learner assessment data exporter used to send to the integrated channel.
            kwargs: Contains integrated channel-specific information for customized transmission variables.
                - app_label: The app label of the integrated channel for whom to store learner data records for.
                - model_name: The name of the specific learner data record model to use.
                - remote_user_id: The remote ID field name of the learner on the audit model.
        """
        TransmissionAudit = apps.get_model(  # pylint: disable=invalid-name
            app_label=kwargs.get('app_label', 'integrated_channel'),
            model_name=kwargs.get('model_name', 'LearnerDataTransmissionAudit'),
        )
        kwargs.update(
            TransmissionAudit=TransmissionAudit,
        )

        # Retrieve learner data for each existing enterprise enrollment under the enterprise customer
        # and transmit the data according to the current enterprise configuration.
        for learner_data in exporter.bulk_assessment_level_export():
            serialized_payload = learner_data.serialize(enterprise_configuration=self.enterprise_configuration)
            enterprise_enrollment_id = learner_data.enterprise_course_enrollment_id

            # Check the last transmission for the current enrollment and see if the old grades match the new ones
            if is_already_transmitted(
                    TransmissionAudit,
                    enterprise_enrollment_id,
                    learner_data.grade,
                    learner_data.subsection_id
            ):
                # We've already sent a completion status for this enrollment
                LOGGER.info('Skipping previously sent enterprise enrollment {}'.format(enterprise_enrollment_id))
                continue

            try:
                code, body = self.client.create_assessment_reporting(
                    getattr(learner_data, kwargs.get('remote_user_id')),
                    serialized_payload
                )
                LOGGER.info(
                    'Successfully sent completion status call for enterprise enrollment {}'.format(
                        enterprise_enrollment_id,
                    )
                )
            except ClientError as client_error:
                code = client_error.status_code
                body = client_error.message
                self.handle_transmission_error(learner_data, client_error)

            learner_data.status = str(code)
            learner_data.error_message = body if code >= 400 else ''

            learner_data.save()

    def transmit(self, payload, **kwargs):
        """
        Send a completion status call to the integrated channel using the client.

        Args:
            payload: The learner completion data payload to send to the integrated channel.
            kwargs: Contains integrated channel-specific information for customized transmission variables.
                - app_label: The app label of the integrated channel for whom to store learner data records for.
                - model_name: The name of the specific learner data record model to use.
                - remote_user_id: The remote ID field name of the learner on the audit model.
        """
        TransmissionAudit = apps.get_model(  # pylint: disable=invalid-name
            app_label=kwargs.get('app_label', 'integrated_channel'),
            model_name=kwargs.get('model_name', 'LearnerDataTransmissionAudit'),
        )
        kwargs.update(
            TransmissionAudit=TransmissionAudit,
        )
        # Since we have started sending courses to integrated channels instead of course runs,
        # we need to attempt to send transmissions with course keys and course run ids in order to
        # ensure that we account for whether courses or course runs exist in the integrated channel.
        # The exporters have been changed to return multiple transmission records to attempt,
        # one by course key and one by course run id.
        # If the transmission with the course key succeeds, the next one will get skipped.
        # If it fails, the one with the course run id will be attempted and (presumably) succeed.
        for learner_data in payload.export(**kwargs):
            serialized_payload = learner_data.serialize(enterprise_configuration=self.enterprise_configuration)
            LOGGER.debug('Attempting to transmit serialized payload: %s', serialized_payload)

            enterprise_enrollment_id = learner_data.enterprise_course_enrollment_id
            if learner_data.completed_timestamp is None:
                # The user has not completed the course, so we shouldn't send a completion status call
                LOGGER.info('Skipping in-progress enterprise enrollment {}'.format(enterprise_enrollment_id))
                continue

            grade = getattr(learner_data, 'grade', None)
            if is_already_transmitted(TransmissionAudit, enterprise_enrollment_id, grade):
                # We've already sent a completion status for this enrollment
                LOGGER.info('Skipping previously sent enterprise enrollment {}'.format(enterprise_enrollment_id))
                continue

            try:
                code, body = self.client.create_course_completion(
                    getattr(learner_data, kwargs.get('remote_user_id')),
                    serialized_payload
                )
                LOGGER.info(
                    'Successfully sent completion status call for enterprise enrollment {}'.format(
                        enterprise_enrollment_id,
                    )
                )
            except ClientError as client_error:
                code = client_error.status_code
                body = client_error.message
                self.handle_transmission_error(learner_data, client_error)

            learner_data.status = str(code)
            learner_data.error_message = body if code >= 400 else ''

            learner_data.save()

    def handle_transmission_error(self, learner_data, client_exception):
        """Handle the case where the transmission fails."""
        LOGGER.exception(
            (
                'Failed to send completion status call for enterprise enrollment %s'
                'with payload %s'
                '\nError message: %s'
                '\nError status code: %s'
            ),
            learner_data.enterprise_course_enrollment_id,
            learner_data,
            client_exception.message,
            client_exception.status_code
        )
