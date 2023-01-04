"""
Serializer for Degreed2 configuration.
"""
from integrated_channels.api.serializers import EnterpriseCustomerPluginConfigSerializer
from integrated_channels.degreed2.models import Degreed2EnterpriseCustomerConfiguration


class Degreed2ConfigSerializer(EnterpriseCustomerPluginConfigSerializer):
    class Meta:
        model = Degreed2EnterpriseCustomerConfiguration
        extra_fields = (
            'client_id',
            'client_secret',
            'degreed_base_url',
            'degreed_token_fetch_base_url',
        )
        fields = EnterpriseCustomerPluginConfigSerializer.Meta.fields + extra_fields
