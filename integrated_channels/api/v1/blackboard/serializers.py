"""
    Serializer for Blackboard configuration.
"""
from rest_framework import serializers

from integrated_channels.api.serializers import EnterpriseCustomerPluginConfigSerializer
from integrated_channels.blackboard.models import (
    BlackboardEnterpriseCustomerConfiguration,
    BlackboardGlobalConfiguration,
)


class BlackboardConfigSerializer(EnterpriseCustomerPluginConfigSerializer):
    oauth_authorization_url = serializers.ReadOnlyField()
    is_valid = serializers.ReadOnlyField()
    channel_code = serializers.ReadOnlyField()
    last_sync_attempted_at = serializers.SerializerMethodField()
    last_content_sync_attempted_at = serializers.SerializerMethodField()
    last_learner_sync_attempted_at = serializers.SerializerMethodField()
    last_sync_errored_at = serializers.SerializerMethodField()
    last_content_sync_errored_at = serializers.SerializerMethodField()
    last_learner_sync_errored_at = serializers.SerializerMethodField()

    class Meta:
        model = BlackboardEnterpriseCustomerConfiguration
        fields = ('id', 'client_id', 'client_secret', 'blackboard_base_url',
                  'refresh_token', 'transmission_chunk_size', 'uuid', 'enterprise_customer',
                  'oauth_authorization_url', 'is_valid', 'channel_code', 'active',
                  'last_sync_attempted_at', 'last_content_sync_attempted_at',
                  'last_learner_sync_attempted_at', 'last_sync_errored_at',
                  'last_content_sync_errored_at', 'last_learner_sync_errored_at')


class BlackboardGlobalConfigSerializer(serializers.ModelSerializer):

    class Meta:
        model = BlackboardGlobalConfiguration
        fields = ('app_key',)
