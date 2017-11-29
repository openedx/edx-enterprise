# -*- coding: utf-8 -*-
"""
Class for transmitting learner data to SuccessFactors.
"""

from __future__ import absolute_import, unicode_literals

from integrated_channels.integrated_channel.transmitters.learner_data import LearnerTransmitter
from integrated_channels.sap_success_factors.client import SAPSuccessFactorsAPIClient


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
