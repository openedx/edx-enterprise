"""
Serializer for Degreed2 configuration.
"""
from rest_framework import serializers

from integrated_channels.integrated_channel.models import (
    ContentMetadataItemTransmission,
    LearnerDataTransmissionAudit,
    GenericLearnerDataTransmissionAudit,
)
from integrated_channels.sap_success_factors.models import SapSuccessFactorsLearnerDataTransmissionAudit


class ContentSyncStatusSerializer(serializers.ModelSerializer):
    channel_code = serializers.ReadOnlyField()

    class Meta:
        model = ContentMetadataItemTransmission
        fields = '__all__'


class LearnerSyncStatusSerializer(serializers.ModelSerializer):

    class Meta:
        model = LearnerDataTransmissionAudit
        fields = '__all__'

    @classmethod
    def get_class_by_channel_code(this_cls, channel_code):
        # this is a qurik of the generic class
        if channel_code.lower() == 'generic':
            channel_code = 'integrated_channel'
        elif channel_code.lower() == 'sap':
            channel_code = 'sap_success_factors'
        for a_cls in this_cls.__subclasses__():
            if a_cls.Meta().model._meta.app_label == channel_code.lower():
                return a_cls
        return None


class GenericLearnerSyncStatusSerializer(LearnerSyncStatusSerializer):

    class Meta:
        model = GenericLearnerDataTransmissionAudit
        fields = '__all__'


class SapLearnerSyncStatusSerializer(LearnerSyncStatusSerializer):

    class Meta:
        model = SapSuccessFactorsLearnerDataTransmissionAudit
        fields = '__all__'