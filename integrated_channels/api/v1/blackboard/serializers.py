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

    class Meta:
        model = BlackboardEnterpriseCustomerConfiguration
        extra_fields = (
            'client_id',
            'client_secret',
            'blackboard_base_url',
            'refresh_token',
            'uuid',
            'oauth_authorization_url',
        )
        fields = EnterpriseCustomerPluginConfigSerializer.Meta.fields + extra_fields


class BlackboardGlobalConfigSerializer(serializers.ModelSerializer):

    class Meta:
        model = BlackboardGlobalConfiguration
        fields = ('app_key',)
