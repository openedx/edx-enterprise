"""
    Serializer for Degreed configuration.
"""
from rest_framework import serializers

from integrated_channels.api.serializers import EnterpriseCustomerPluginConfigSerializer
from integrated_channels.degreed.models import DegreedEnterpriseCustomerConfiguration


class DegreedConfigSerializer(EnterpriseCustomerPluginConfigSerializer):
    is_valid = serializers.ReadOnlyField()
    channel_code = serializers.ReadOnlyField()
    last_sync_attemped_at = serializers.ReadOnlyField()
    last_content_sync_attempted_at  = serializers.ReadOnlyField()
    last_learner_sync_attempted_at = serializers.ReadOnlyField()
    last_sync_errored_at = serializers.ReadOnlyField()
    last_content_sync_errored_at = serializers.ReadOnlyField()
    last_learner_sync_errored_at = serializers.ReadOnlyField()

    class Meta:
        extra_fields = ('key', 'secret', 'degreed_company_id', 'degreed_base_url', 'channel_code',
                        'degreed_user_id', 'degreed_user_password', 'provider_id', 'is_valid')
        model = DegreedEnterpriseCustomerConfiguration
        fields = EnterpriseCustomerPluginConfigSerializer.Meta.fields + extra_fields
