"""
Class for transmitting learner data to SuccessFactors.
"""
from __future__ import absolute_import, unicode_literals
import logging
from django.apps import apps
from integrated_channels.sap_success_factors.transmitters import SuccessFactorsTransmitterBase
from requests import RequestException


LOGGER = logging.getLogger(__name__)


class SuccessFactorsLearnerDataTransmitter(SuccessFactorsTransmitterBase):
    """
    This endpoint is intended to receive learner data routed from the integrated_channel app that is ready to be
    sent to SuccessFactors.
    """

    def transmit(self, payload):
        """
        Send a completion status call to SAP SuccessFactors using the client.

        Args:
            payload (LearnerDataTransmissionAudit): The learner completion data payload to send to SAP SuccessFactors
        """
        serialized_payload = payload.serialize()
        LOGGER.info(serialized_payload)

        enterprise_enrollment_id = payload.enterprise_course_enrollment_id
        if payload.completed_timestamp is None:
            # The user has not completed the course, so we shouldn't send a completion status call
            LOGGER.debug('Skipping in progress enterprise enrollment {}'.format(enterprise_enrollment_id))
            return None

        LearnerDataTransmissionAudit = apps.get_model(  # pylint: disable=invalid-name
            app_label='sap_success_factors',
            model_name='LearnerDataTransmissionAudit'
        )

        previous_transmissions = LearnerDataTransmissionAudit.objects.filter(
            enterprise_course_enrollment_id=enterprise_enrollment_id,
            completed_timestamp=payload.completed_timestamp,
            error_message=''
        )
        if previous_transmissions.exists():
            # We've already sent a completion status call for this enrollment and certificate generation
            LOGGER.debug('Skipping previously sent enterprise enrollment {}'.format(enterprise_enrollment_id))
            return None

        try:
            code, body = self.client.send_completion_status(payload.sapsf_user_id, serialized_payload)
            LOGGER.debug('Successfully sent completion status call for enterprise enrollment {} with payload {}'.
                         format(enterprise_enrollment_id, serialized_payload))
        except RequestException as request_exception:
            code = 500
            body = str(request_exception)
            LOGGER.error('Failed to send completion status call for enterprise enrollment {} with payload {}'
                         '\nError message: {}'.format(enterprise_enrollment_id, payload, body))

        payload.status = str(code)
        payload.error_message = body if code >= 400 else ''
        payload.save()
        return payload
