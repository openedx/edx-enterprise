"""
Serializer for integrated channel api.
"""

from rest_framework import serializers

from integrated_channels.integrated_channel.models import EnterpriseCustomerPluginConfiguration


class EnterpriseCustomerPluginConfigSerializer(serializers.ModelSerializer):
    """
    Serializer for EnterpriseCustomerPluginConfiguration model
    """
    is_valid = serializers.ReadOnlyField()
    channel_code = serializers.ReadOnlyField()
    last_sync_attempted_at = serializers.ReadOnlyField()
    last_content_sync_attempted_at = serializers.ReadOnlyField()
    last_learner_sync_attempted_at = serializers.ReadOnlyField()
    last_sync_errored_at = serializers.ReadOnlyField()
    last_content_sync_errored_at = serializers.ReadOnlyField()
    last_learner_sync_errored_at = serializers.ReadOnlyField()
    last_modified_at = serializers.ReadOnlyField()

    class Meta:
        model = EnterpriseCustomerPluginConfiguration
        fields = (
            'id',
            'display_name',
            'channel_code',
            'enterprise_customer',
            'idp_id',
            'active',
            'is_valid',
            'last_sync_attempted_at',
            'last_content_sync_attempted_at',
            'last_learner_sync_attempted_at',
            'last_sync_errored_at',
            'last_content_sync_errored_at',
            'last_learner_sync_errored_at',
            'transmission_chunk_size',
            'last_modified_at',
        )
