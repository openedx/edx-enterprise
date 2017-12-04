# -*- coding: utf-8 -*-
"""
Generic learner data transmitter for integrated channels.
"""

from __future__ import absolute_import, unicode_literals

import logging

from integrated_channels.integrated_channel.client import IntegratedChannelApiClient
from integrated_channels.integrated_channel.transmitters import Transmitter
from requests import RequestException

from django.apps import apps

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
        super(LearnerTransmitter, self).__init__(
            enterprise_configuration=enterprise_configuration,
            client=client
        )

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
        IntegratedChannelLearnerDataTransmissionAudit = apps.get_model(  # pylint: disable=invalid-name
            app_label=kwargs.get('app_label', 'integrated_channel'),
            model_name=kwargs.get('model_name', 'LearnerDataTransmissionAudit'),
        )
        for learner_data in payload.export():
            serialized_payload = learner_data.serialize(enterprise_configuration=self.enterprise_configuration)
            LOGGER.info('Attempting to transmit serialized payload: %s', serialized_payload)

            enterprise_enrollment_id = learner_data.enterprise_course_enrollment_id
            if learner_data.completed_timestamp is None:
                # The user has not completed the course, so we shouldn't send a completion status call
                LOGGER.info('Skipping in-progress enterprise enrollment {}'.format(enterprise_enrollment_id))
                continue

            previous_transmissions = IntegratedChannelLearnerDataTransmissionAudit.objects.filter(
                enterprise_course_enrollment_id=enterprise_enrollment_id,
                error_message=''
            )
            if previous_transmissions.exists():
                # We've already sent a completion status call for this enrollment
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
            except RequestException as request_exception:
                code = 500
                body = str(request_exception)
                try:
                    sys_msg = request_exception.response.content
                except AttributeError:
                    sys_msg = 'Not available'
                LOGGER.error(
                    (
                        'Failed to send completion status call for enterprise enrollment %s'
                        'with payload %s'
                        '\nError message: %s'
                        '\nSystem message: %s'
                    ),
                    enterprise_enrollment_id,
                    learner_data,
                    body,
                    sys_msg
                )

            learner_data.status = str(code)
            learner_data.error_message = body if code >= 400 else ''
            learner_data.save()
