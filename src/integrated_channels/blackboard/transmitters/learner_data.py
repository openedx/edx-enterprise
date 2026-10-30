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
        super().__init__(
            enterprise_configuration=enterprise_configuration,
            client=client
        )

    def transmit(self, payload, **kwargs):
        """
        Send a completion status call to Blackboard using the client.

        Args:
            payload: The learner completion exporter for Blackboard
        """
        kwargs['app_label'] = 'blackboard'
        kwargs['model_name'] = 'BlackboardLearnerDataTransmissionAudit'
        kwargs['remote_user_id'] = 'blackboard_user_email'
        super().transmit(payload, **kwargs)

    def single_learner_assessment_grade_transmit(self, exporter, **kwargs):
        """
        Send an assessment level grade update status call for a single enterprise learner to blackboard using the
        client.
        Args:
            exporter: The learner completion data payload to send to blackboard
        """
        kwargs['app_label'] = 'blackboard'
        kwargs['model_name'] = 'BlackboardLearnerAssessmentDataTransmissionAudit'
        kwargs['remote_user_id'] = 'blackboard_user_email'
        super().single_learner_assessment_grade_transmit(exporter, **kwargs)

    def assessment_level_transmit(self, exporter, **kwargs):
        """
        Send a bulk assessment level grade update status call to blackboard using the client.
        Args:
            exporter: The learner completion data payload to send to blackboard
        """
        kwargs['app_label'] = 'blackboard'
        kwargs['model_name'] = 'BlackboardLearnerAssessmentDataTransmissionAudit'
        kwargs['remote_user_id'] = 'blackboard_user_email'
        super().assessment_level_transmit(exporter, **kwargs)
