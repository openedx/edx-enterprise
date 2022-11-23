"""
    Serializer for Degreed configuration.
"""
from rest_framework import serializers

from integrated_channels.api.serializers import EnterpriseCustomerPluginConfigSerializer
from integrated_channels.degreed.models import DegreedEnterpriseCustomerConfiguration


class DegreedConfigSerializer(EnterpriseCustomerPluginConfigSerializer):
    is_valid = serializers.ReadOnlyField()
    channel_code = serializers.ReadOnlyField()
    last_sync_attempted_at = serializers.SerializerMethodField()
    last_content_sync_attempted_at = serializers.SerializerMethodField()
    last_learner_sync_attempted_at = serializers.SerializerMethodField()
    last_sync_errored_at = serializers.SerializerMethodField()
    last_content_sync_errored_at = serializers.SerializerMethodField()
    last_learner_sync_errored_at = serializers.SerializerMethodField()

    class Meta:
        model = DegreedEnterpriseCustomerConfiguration
        fields = ('id', 'key', 'secret', 'degreed_company_id', 'degreed_base_url', 'channel_code',
                  'degreed_user_id', 'degreed_user_password', 'provider_id', 'is_valid', 'enterprise_customer',
                  'last_sync_attempted_at', 'last_content_sync_attempted_at', 'last_learner_sync_attempted_at',
                  'last_sync_errored_at', 'last_content_sync_errored_at', 'last_learner_sync_errored_at')
