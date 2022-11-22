"""
    Serializer for Moodle configuration.
"""
from rest_framework import serializers

from integrated_channels.api.serializers import EnterpriseCustomerPluginConfigSerializer
from integrated_channels.moodle.models import MoodleEnterpriseCustomerConfiguration


class MoodleConfigSerializer(EnterpriseCustomerPluginConfigSerializer):
    is_valid = serializers.ReadOnlyField()
    channel_code = serializers.ReadOnlyField()
    last_sync_attempted_at = serializers.SerializerMethodField()
    last_content_sync_attempted_at = serializers.SerializerMethodField()
    last_learner_sync_attempted_at = serializers.SerializerMethodField()
    last_sync_errored_at = serializers.SerializerMethodField()
    last_content_sync_errored_at = serializers.SerializerMethodField()
    last_learner_sync_errored_at = serializers.SerializerMethodField()

    class Meta:
        model = MoodleEnterpriseCustomerConfiguration
        fields = ('id', 'moodle_base_url', 'service_short_name', 'category_id', 'username', 'enterprise_customer',
                  'password', 'token', 'transmission_chunk_size', 'is_valid', 'channel_code',
                  'last_sync_attempted_at', 'last_content_sync_attempted_at', 'last_learner_sync_attempted_at',
                  'last_sync_errored_at', 'last_content_sync_errored_at', 'last_learner_sync_errored_at')
