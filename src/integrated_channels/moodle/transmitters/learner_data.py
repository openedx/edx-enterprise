"""
Class for transmitting learner data to Moodle.
"""

from integrated_channels.integrated_channel.transmitters.learner_data import LearnerTransmitter
from integrated_channels.moodle.client import MoodleAPIClient


class MoodleLearnerTransmitter(LearnerTransmitter):
    """
    This endpoint is intended to receive learner data routed from the integrated_channel app that is ready to be
    sent to Moodle.
    """

    def __init__(self, enterprise_configuration, client=MoodleAPIClient):
        """
        By default, use the ``MoodleAPIClient`` for learner data transmission to Moodle.
        """
        super().__init__(
            enterprise_configuration=enterprise_configuration,
            client=client
        )

    def transmit(self, payload, **kwargs):
        """
        Send a completion status call to Moodle using the client.

        Args:
            payload: The learner data exporter for Moodle
        """
        kwargs['app_label'] = 'moodle'
        kwargs['model_name'] = 'MoodleLearnerDataTransmissionAudit'
        kwargs['remote_user_id'] = 'moodle_user_email'
        super().transmit(payload, **kwargs)
