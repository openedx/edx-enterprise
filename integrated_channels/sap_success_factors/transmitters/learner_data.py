# -*- coding: utf-8 -*-
"""
Class for transmitting learner data to SuccessFactors.
"""

from __future__ import absolute_import, unicode_literals

import logging

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
        super(SapSuccessFactorsLearnerTransmitter, self).__init__(
            enterprise_configuration=enterprise_configuration,
            client=client
        )

    def transmit(self, payload, **kwargs):
        """
        Send a completion status call to SAP SuccessFactors using the client.

        Args:
            payload: The learner completion data payload to send to SAP SuccessFactors
        """
        kwargs['app_label'] = 'sap_success_factors'
        kwargs['model_name'] = 'SapSuccessFactorsLearnerDataTransmissionAudit'
        kwargs['remote_user_id'] = 'sapsf_user_id'
        super(SapSuccessFactorsLearnerTransmitter, self).transmit(payload, **kwargs)

    def handle_transmission_error(self, learner_data, request_exception):
        """Handle the case where the employee on SAPSF's side is marked as inactive."""
        try:
            sys_msg = request_exception.response.content
        except AttributeError:
            pass
        else:
            if 'user account is inactive' in sys_msg:
                ecu = EnterpriseCustomerUser.objects.get(
                    enterprise_enrollments__id=learner_data.enterprise_course_enrollment_id)
                ecu.active = False
                ecu.save()
                LOGGER.warning(
                    'User %s with ID %s and email %s is a former employee of %s '
                    'and has been marked inactive in SAPSF. Now marking inactive internally.',
                    ecu.username, ecu.user_id, ecu.user_email, ecu.enterprise_customer
                )
                return
        super(SapSuccessFactorsLearnerTransmitter, self).handle_transmission_error(learner_data, request_exception)
