# -*- coding: utf-8 -*-
"""
Class for transmitting learner data to Blackboard.
"""

from integrated_channels.blackboard.client import BlackboardAPIClient
from integrated_channels.integrated_channel.transmitters.learner_data import LearnerTransmitter


class BlackboardLearnerTransmitter(LearnerTransmitter):
    """
    This endpoint is intended to receive learner data routed from the integrated_channel app that is ready to be
    sent to Blackboard.
    """

    def __init__(self, enterprise_configuration, client=BlackboardAPIClient):
        """
        By default, use the ``BlackboardAPIClient`` for learner data transmission to Blackboard.
        """
        super(BlackboardLearnerTransmitter, self).__init__(
            enterprise_configuration=enterprise_configuration,
            client=client
        )

    def transmit(self, payload, **kwargs):
        """
        Send a completion status call to Blackboard using the client.

        Args:
            payload: The learner completion data payload to send to Blackboard
        """
        kwargs['app_label'] = 'blackboard'
        kwargs['model_name'] = 'BlackboardLearnerDataTransmissionAudit'
        kwargs['remote_user_id'] = 'blackboard_user_email'
        super(BlackboardLearnerTransmitter, self).transmit(payload, **kwargs)
