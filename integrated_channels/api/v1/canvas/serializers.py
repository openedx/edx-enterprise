"""
Serializers for Canvas.
"""
from rest_framework import serializers

from integrated_channels.api.serializers import EnterpriseCustomerPluginConfigSerializer
from integrated_channels.canvas.models import CanvasEnterpriseCustomerConfiguration


class CanvasEnterpriseCustomerConfigurationSerializer(EnterpriseCustomerPluginConfigSerializer):
    class Meta:
        model = CanvasEnterpriseCustomerConfiguration
        extra_fields = (
            'encrypted_client_id',
            'encrypted_client_secret',
            'canvas_account_id',
            'canvas_base_url',
            'refresh_token',
            'uuid',
            'oauth_authorization_url',
        )
        fields = EnterpriseCustomerPluginConfigSerializer.Meta.fields + extra_fields

    encrypted_client_id = serializers.CharField(required=False, allow_blank=False, read_only=False)
    encrypted_client_secret = serializers.CharField(required=False, allow_blank=False, read_only=False)
