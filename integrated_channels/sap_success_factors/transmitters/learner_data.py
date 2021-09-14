# -*- coding: utf-8 -*-
"""
Class for transmitting learner data to SuccessFactors.
"""

import logging

import six

from enterprise.models import EnterpriseCustomerUser
from integrated_channels.integrated_channel.transmitters.learner_data import LearnerTransmitter
from integrated_channels.sap_success_factors.client import SAPSuccessFactorsAPIClient

LOGGER = logging.getLogger(__name__)


class SapSuccessFactorsLearnerTransmitter(LearnerTransmitter):
    """
    This endpoint is intended to receive learner data routed from the integrated_channel app that is ready to be
    sent to SuccessFactors.
    """

    def __init__(self, enterprise_configuration, client=SAPSuccessFactorsAPIClient):
        """
        By default, use the ``SAPSuccessFactorsAPIClient`` for learner data transmission to SAPSF.
        """
        super().__init__(
            enterprise_configuration=enterprise_configuration,
            client=client
        )

    def transmit(self, payload, **kwargs):
        """
        Send a completion status call to SAP SuccessFactors using the client.

        Args:
            payload: The learner data exporter for SAP SuccessFactors
        """
        kwargs['app_label'] = 'sap_success_factors'
        kwargs['model_name'] = 'SapSuccessFactorsLearnerDataTransmissionAudit'
        kwargs['remote_user_id'] = 'sapsf_user_id'
        super().transmit(payload, **kwargs)

    def handle_transmission_error(self, learner_data, client_exception, integrated_channel_name,
                                  enterprise_customer_uuid, learner_id, course_id):
        """Handle the case where the employee on SAPSF's side is marked as inactive."""
        try:
            sys_msg = six.text_type(client_exception.message)
            ecu = EnterpriseCustomerUser.objects.get(
                enterprise_enrollments__id=learner_data.enterprise_course_enrollment_id)

        except AttributeError:
            pass
        else:
            if sys_msg and 'user account is inactive' in sys_msg:
                ecu.active = False
                ecu.save()
                LOGGER.warning(
                    'User with LMS ID %s, ECU ID %s is a former employee of %s '
                    'and has been marked inactive in SAPSF. Now marking inactive internally.',
                    ecu.user_id, ecu.id, ecu.enterprise_customer
                )
                return
        super().handle_transmission_error(learner_data, client_exception,
                                          integrated_channel_name, enterprise_customer_uuid, learner_id, course_id)
