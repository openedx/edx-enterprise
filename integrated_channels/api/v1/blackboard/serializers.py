"""
    Serializer for Blackboard configuration.
"""
from integrated_channels.api.serializers import EnterpriseCustomerPluginConfigSerializer
from rest_framework import serializers

from integrated_channels.blackboard.models import (
    BlackboardEnterpriseCustomerConfiguration,
    BlackboardGlobalConfiguration,
)


class BlackboardConfigSerializer(EnterpriseCustomerPluginConfigSerializer):
    oauth_authorization_url = serializers.ReadOnlyField()
    is_valid = serializers.ReadOnlyField()
    channel_code = serializers.ReadOnlyField()

    class Meta:
        extra_fields = ('client_id', 'client_secret', 'blackboard_base_url',
                        'refresh_token', 'transmission_chunk_size', 'uuid',
                        'oauth_authorization_url', 'is_valid', 'channel_code')
        model = BlackboardEnterpriseCustomerConfiguration
        fields = EnterpriseCustomerPluginConfigSerializer.Meta.fields + extra_fields


class BlackboardGlobalConfigSerializer(serializers.ModelSerializer):

    class Meta:
        model = BlackboardGlobalConfiguration
        fields = ('app_key',)
