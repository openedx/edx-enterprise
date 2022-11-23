"""
Serializer for Degreed2 configuration.
"""
from rest_framework import serializers

from integrated_channels.api.serializers import EnterpriseCustomerPluginConfigSerializer
from integrated_channels.degreed2.models import Degreed2EnterpriseCustomerConfiguration


class Degreed2ConfigSerializer(EnterpriseCustomerPluginConfigSerializer):
    is_valid = serializers.ReadOnlyField()
    channel_code = serializers.ReadOnlyField()
    last_sync_attempted_at = serializers.SerializerMethodField()
    last_content_sync_attempted_at = serializers.SerializerMethodField()
    last_learner_sync_attempted_at = serializers.SerializerMethodField()
    last_sync_errored_at = serializers.SerializerMethodField()
    last_content_sync_errored_at = serializers.SerializerMethodField()
    last_learner_sync_errored_at = serializers.SerializerMethodField()

    class Meta:
        model = Degreed2EnterpriseCustomerConfiguration
        fields = ('id', 'client_id', 'client_secret', 'degreed_base_url', 'degreed_token_fetch_base_url',
                  'transmission_chunk_size', 'is_valid', 'channel_code', 'enterprise_customer',
                  'last_sync_attempted_at', 'last_content_sync_attempted_at', 'last_learner_sync_attempted_at',
                  'last_sync_errored_at', 'last_content_sync_errored_at', 'last_learner_sync_errored_at')
