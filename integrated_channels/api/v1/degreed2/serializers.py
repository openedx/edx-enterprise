"""
Serializer for Degreed2 configuration.
"""
from integrated_channels.api.serializers import EnterpriseCustomerPluginConfigSerializer
from rest_framework import serializers

from integrated_channels.degreed2.models import Degreed2EnterpriseCustomerConfiguration


class Degreed2ConfigSerializer(EnterpriseCustomerPluginConfigSerializer):
    is_valid = serializers.ReadOnlyField()
    channel_code = serializers.ReadOnlyField()

    class Meta:
        extra_fields = ('client_id', 'client_secret', 'degreed_base_url', 'degreed_token_fetch_base_url',
                        'transmission_chunk_size', 'is_valid', 'channel_code')
        model = Degreed2EnterpriseCustomerConfiguration
        fields = EnterpriseCustomerPluginConfigSerializer.Meta.fields + extra_fields
