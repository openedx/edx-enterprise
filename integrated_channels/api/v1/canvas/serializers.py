"""
Serializers for Canvas.
"""
from integrated_channels.api.serializers import EnterpriseCustomerPluginConfigSerializer
from integrated_channels.canvas.models import CanvasEnterpriseCustomerConfiguration


class CanvasEnterpriseCustomerConfigurationSerializer(EnterpriseCustomerPluginConfigSerializer):
    class Meta:
        model = CanvasEnterpriseCustomerConfiguration
        extra_fields = (
            'client_id',
            'client_secret',
            'canvas_account_id',
            'canvas_base_url',
            'refresh_token',
            'uuid',
            'oauth_authorization_url',
        )
        fields = EnterpriseCustomerPluginConfigSerializer.Meta.fields + extra_fields
