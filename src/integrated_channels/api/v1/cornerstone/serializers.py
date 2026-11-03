"""
    Serializer for Cornerstone configuration.
"""
from integrated_channels.api.serializers import EnterpriseCustomerPluginConfigSerializer
from integrated_channels.cornerstone.models import CornerstoneEnterpriseCustomerConfiguration


class CornerstoneConfigSerializer(EnterpriseCustomerPluginConfigSerializer):
    class Meta:
        model = CornerstoneEnterpriseCustomerConfiguration
        extra_fields = (
            'cornerstone_base_url',
            'session_token',
            'session_token_modified'
        )
        fields = EnterpriseCustomerPluginConfigSerializer.Meta.fields + extra_fields
