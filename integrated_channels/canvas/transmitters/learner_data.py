# -*- coding: utf-8 -*-
"""
Class for transmitting learner data to Canvas.
"""

from integrated_channels.canvas.client import CanvasAPIClient
from integrated_channels.integrated_channel.transmitters.learner_data import LearnerTransmitter


class CanvasLearnerTransmitter(LearnerTransmitter):
    """
    This endpoint is intended to receive learner data routed from the integrated_channel app that is ready to be
    sent to Canvas.
    """

    def __init__(self, enterprise_configuration, client=CanvasAPIClient):
        """
        By default, use the ``CanvasAPIClient`` for learner data transmission to Canvas.
        """
        super().__init__(
            enterprise_configuration=enterprise_configuration,
            client=client
        )

    def transmit(self, payload, **kwargs):
        """
        Send a completion status call to Canvas using the client.

        Args:
            payload: The learner completion data payload to send to Canvas
        """
        kwargs['app_label'] = 'canvas'
        kwargs['model_name'] = 'CanvasLearnerDataTransmissionAudit'
        kwargs['remote_user_id'] = 'canvas_user_email'
        super().transmit(payload, **kwargs)

    def single_learner_assessment_grade_transmit(self, exporter, **kwargs):
        """
        Send an assessment level grade update status call for a single enterprise learner to Canvas using the client.

        Args:
            payload: The learner completion data payload to send to Canvas
        """
        kwargs['app_label'] = 'canvas'
        kwargs['model_name'] = 'CanvasLearnerDataTransmissionAudit'
        kwargs['remote_user_id'] = 'canvas_user_email'
        super().single_learner_assessment_grade_transmit(exporter, **kwargs)

    def assessment_level_transmit(self, exporter, **kwargs):
        """
        Send a bulk assessment level grade update status call to Canvas using the client.

        Args:
            payload: The learner completion data payload to send to Canvas
        """
        kwargs['app_label'] = 'canvas'
        kwargs['model_name'] = 'CanvasLearnerDataTransmissionAudit'
        kwargs['remote_user_id'] = 'canvas_user_email'
        super().assessment_level_transmit(exporter, **kwargs)
