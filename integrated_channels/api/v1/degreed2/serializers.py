"""
Serializer for Degreed2 configuration.
"""
from rest_framework import serializers

from integrated_channels.api.serializers import EnterpriseCustomerPluginConfigSerializer
from integrated_channels.degreed2.models import Degreed2EnterpriseCustomerConfiguration


class Degreed2ConfigSerializer(EnterpriseCustomerPluginConfigSerializer):
    class Meta:
        model = Degreed2EnterpriseCustomerConfiguration
        extra_fields = (
            'encrypted_client_id',
            'encrypted_client_secret',
            'degreed_base_url',
            'degreed_token_fetch_base_url',
        )
        fields = EnterpriseCustomerPluginConfigSerializer.Meta.fields + extra_fields

    encrypted_client_id = serializers.CharField(required=False, allow_blank=False, read_only=False)
    encrypted_client_secret = serializers.CharField(required=False, allow_blank=False, read_only=False)
