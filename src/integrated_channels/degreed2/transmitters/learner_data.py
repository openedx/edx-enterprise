# -*- coding: utf-8 -*-
"""
Class for transmitting learner data to Degreed2.
"""

from integrated_channels.degreed2.client import Degreed2APIClient
from integrated_channels.integrated_channel.transmitters.learner_data import LearnerTransmitter


class Degreed2LearnerTransmitter(LearnerTransmitter):
    """
    This endpoint is intended to receive learner data routed from the integrated_channel app that is ready to be
    sent to Degreed2.
    """

    def __init__(self, enterprise_configuration, client=Degreed2APIClient):
        """
        By default, use the ``DegreedAPIClient`` for learner data transmission to Degreed.
        """
        super().__init__(
            enterprise_configuration=enterprise_configuration,
            client=client
        )

    def transmit(self, payload, **kwargs):
        """
        Send a completion status call to Degreed using the client.

        Args:
            payload: The learner exporter for Degreed
        """
        kwargs['app_label'] = 'degreed2'
        kwargs['model_name'] = 'Degreed2LearnerDataTransmissionAudit'
        kwargs['remote_user_id'] = 'degreed_user_email'
        super().transmit(payload, **kwargs)
