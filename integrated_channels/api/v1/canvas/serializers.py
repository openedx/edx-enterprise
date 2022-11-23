"""
Serializers for Canvas.
"""
from rest_framework import serializers

from integrated_channels.api.serializers import EnterpriseCustomerPluginConfigSerializer
from integrated_channels.canvas.models import CanvasEnterpriseCustomerConfiguration


class CanvasEnterpriseCustomerConfigurationSerializer(EnterpriseCustomerPluginConfigSerializer):
    is_valid = serializers.ReadOnlyField()
    channel_code = serializers.ReadOnlyField()
    last_sync_attempted_at = serializers.SerializerMethodField()
    last_content_sync_attempted_at = serializers.SerializerMethodField()
    last_learner_sync_attempted_at = serializers.SerializerMethodField()
    last_sync_errored_at = serializers.SerializerMethodField()
    last_content_sync_errored_at = serializers.SerializerMethodField()
    last_learner_sync_errored_at = serializers.SerializerMethodField()

    class Meta:
        model = CanvasEnterpriseCustomerConfiguration
        fields = ('id', 'client_id', 'client_secret', 'canvas_account_id', 'canvas_base_url',
                  'refresh_token', 'transmission_chunk_size', 'uuid', 'channel_code',
                  'enterprise_customer', 'oauth_authorization_url', 'is_valid', 'active',
                  'last_sync_attempted_at', 'last_content_sync_attempted_at',
                  'last_learner_sync_attempted_at', 'last_sync_errored_at',
                  'last_content_sync_errored_at', 'last_learner_sync_errored_at')
