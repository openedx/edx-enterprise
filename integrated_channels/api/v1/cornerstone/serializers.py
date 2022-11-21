"""
    Serializer for Cornerstone configuration.
"""
from rest_framework import serializers

from integrated_channels.api.serializers import EnterpriseCustomerPluginConfigSerializer
from integrated_channels.cornerstone.models import CornerstoneEnterpriseCustomerConfiguration


class CornerstoneConfigSerializer(EnterpriseCustomerPluginConfigSerializer):
    is_valid = serializers.ReadOnlyField()
    channel_code = serializers.ReadOnlyField()
    last_sync_attemped_at = serializers.ReadOnlyField()
    last_content_sync_attempted_at  = serializers.ReadOnlyField()
    last_learner_sync_attempted_at = serializers.ReadOnlyField()
    last_sync_errored_at = serializers.ReadOnlyField()
    last_content_sync_errored_at = serializers.ReadOnlyField()
    last_learner_sync_errored_at = serializers.ReadOnlyField()

    class Meta:
        extra_fields = ('cornerstone_base_url', 'session_token', 'session_token_modified', 'is_valid', 'channel_code')
        model = CornerstoneEnterpriseCustomerConfiguration
        fields = EnterpriseCustomerPluginConfigSerializer.Meta.fields + extra_fields
