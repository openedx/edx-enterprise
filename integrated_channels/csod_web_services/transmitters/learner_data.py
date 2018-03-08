# -*- coding: utf-8 -*-
"""
Class for transmitting learner data to Cornerstone.
"""

from __future__ import absolute_import, unicode_literals

from integrated_channels.csod_web_services.client import CSODWebServicesAPIClient
from integrated_channels.integrated_channel.transmitters.learner_data import LearnerTransmitter


class CSODWebServicesLearnerTransmitter(LearnerTransmitter):
    """
    This endpoint is intended to receive learner data routed from the integrated_channel app that is ready to be
    sent to Degreed.
    """

    def __init__(self, enterprise_configuration, client=CSODWebServicesAPIClient):
        """
        By default, use the ``CSODWebServicesAPIClient`` for learner data transmission to Cornerstone.
        """
        super(CSODWebServicesLearnerTransmitter, self).__init__(
            enterprise_configuration=enterprise_configuration,
            client=client
        )
