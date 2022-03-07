"""
    Serializer for Blackboard configuration.
"""
from rest_framework import serializers

from integrated_channels.blackboard.models import (
    BlackboardEnterpriseCustomerConfiguration,
    BlackboardGlobalConfiguration,
)


class BlackboardConfigSerializer(serializers.ModelSerializer):
    oauth_authorization_url = serializers.ReadOnlyField()
    is_valid = serializers.ReadOnlyField()
    channel_code = serializers.ReadOnlyField()

    class Meta:
        model = BlackboardEnterpriseCustomerConfiguration
        fields = '__all__'


class BlackboardGlobalConfigSerializer(serializers.ModelSerializer):

    class Meta:
        model = BlackboardGlobalConfiguration
        fields = ('app_key',)
