# -*- coding: utf-8 -*-
"""
Class for transmitting learner data to Degreed.
"""

from __future__ import absolute_import, unicode_literals

from integrated_channels.degreed.client import DegreedAPIClient
from integrated_channels.integrated_channel.transmitters.learner_data import LearnerTransmitter


class DegreedLearnerTransmitter(LearnerTransmitter):
    """
    This endpoint is intended to receive learner data routed from the integrated_channel app that is ready to be
    sent to Degreed.
    """

    def __init__(self, enterprise_configuration, client=DegreedAPIClient):
        """
        By default, use the ``DegreedAPIClient`` for learner data transmission to Degreed.
        """
        super(DegreedLearnerTransmitter, self).__init__(
            enterprise_configuration=enterprise_configuration,
            client=client
        )

    def transmit(self, payload, **kwargs):
        """
        Send a completion status call to Degreed using the client.

        Args:
            payload: The learner completion data payload to send to Degreed
        """
        kwargs['app_label'] = 'degreed'
        kwargs['model_name'] = 'DegreedLearnerDataTransmissionAudit'
        kwargs['remote_user_id'] = 'degreed_user_email'
        super(DegreedLearnerTransmitter, self).transmit(payload, **kwargs)
