"""
Serializer for Degreed2 configuration.
"""
from rest_framework import serializers

from integrated_channels.blackboard.models import BlackboardLearnerDataTransmissionAudit
from integrated_channels.canvas.models import CanvasLearnerDataTransmissionAudit
from integrated_channels.cornerstone.models import CornerstoneLearnerDataTransmissionAudit
from integrated_channels.degreed2.models import Degreed2LearnerDataTransmissionAudit
from integrated_channels.degreed.models import DegreedLearnerDataTransmissionAudit
from integrated_channels.integrated_channel.models import (
    ContentMetadataItemTransmission,
    GenericLearnerDataTransmissionAudit,
    LearnerDataTransmissionAudit,
)
from integrated_channels.moodle.models import MoodleLearnerDataTransmissionAudit
from integrated_channels.sap_success_factors.models import SapSuccessFactorsLearnerDataTransmissionAudit
from integrated_channels.utils import channel_code_to_app_label


class ContentSyncStatusSerializer(serializers.ModelSerializer):

    class Meta:
        model = ContentMetadataItemTransmission
        fields = '__all__'


class LearnerSyncStatusSerializer(serializers.ModelSerializer):
    """
    A base sync-status serializer class for LearnerDataTransmissionAudit implementations.
    """

    class Meta:
        model = LearnerDataTransmissionAudit
        fields = '__all__'

    @classmethod
    def get_class_by_channel_code(this_cls, channel_code):
        """
        return the `LearnerDataTransmissionAudit` sync-status serializer for a particular channel_code
        """
        app_label = channel_code_to_app_label(channel_code)
        for a_cls in this_cls.__subclasses__():
            if a_cls.Meta().model._meta.app_label == app_label:
                return a_cls
        return None


class GenericLearnerSyncStatusSerializer(LearnerSyncStatusSerializer):
    """
    `GenericLearnerDataTransmissionAudit` sync-status serializer
    """

    class Meta:
        model = GenericLearnerDataTransmissionAudit
        fields = '__all__'


class BlackboardLearnerSyncStatusSerializer(LearnerSyncStatusSerializer):
    """
    `BlackboardLearnerDataTransmissionAudit` sync-status serializer
    """

    class Meta:
        model = BlackboardLearnerDataTransmissionAudit
        fields = '__all__'


class CanvasLearnerSyncStatusSerializer(LearnerSyncStatusSerializer):
    """
    `CanvasLearnerDataTransmissionAudit` sync-status serializer
    """

    class Meta:
        model = CanvasLearnerDataTransmissionAudit
        fields = '__all__'


class CornerstoneLearnerSyncStatusSerializer(LearnerSyncStatusSerializer):
    """
    `CornerstoneLearnerDataTransmissionAudit` sync-status serializer
    """

    class Meta:
        model = CornerstoneLearnerDataTransmissionAudit
        fields = '__all__'


class DegreedLearnerSyncStatusSerializer(LearnerSyncStatusSerializer):
    """
    `DegreedLearnerDataTransmissionAudit` sync-status serializer
    """

    class Meta:
        model = DegreedLearnerDataTransmissionAudit
        fields = '__all__'


class Degreed2LearnerSyncStatusSerializer(LearnerSyncStatusSerializer):
    """
    `Degreed2LearnerDataTransmissionAudit` sync-status serializer
    """

    class Meta:
        model = Degreed2LearnerDataTransmissionAudit
        fields = '__all__'


class MoodleLearnerSyncStatusSerializer(LearnerSyncStatusSerializer):
    """
    `MoodleLearnerDataTransmissionAudit` sync-status serializer
    """

    class Meta:
        model = MoodleLearnerDataTransmissionAudit
        fields = '__all__'


class SapLearnerSyncStatusSerializer(LearnerSyncStatusSerializer):
    """
    `SapSuccessFactorsLearnerDataTransmissionAudit` sync-status serializer
    """

    class Meta:
        model = SapSuccessFactorsLearnerDataTransmissionAudit
        fields = '__all__'
