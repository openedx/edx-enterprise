"""
    Serializer for Moodle configuration.
"""
from rest_framework import serializers

from integrated_channels.api.serializers import EnterpriseCustomerPluginConfigSerializer
from integrated_channels.moodle.models import MoodleEnterpriseCustomerConfiguration


class MoodleConfigSerializer(EnterpriseCustomerPluginConfigSerializer):
    is_valid = serializers.ReadOnlyField()
    channel_code = serializers.ReadOnlyField()

    class Meta:
        extra_fields = ('moodle_base_url', 'service_short_name', 'category_id', 'username',
                        'password', 'token', 'transmission_chunk_size', 'is_valid', 'channel_code')
        model = MoodleEnterpriseCustomerConfiguration
        fields = EnterpriseCustomerPluginConfigSerializer.Meta.fields + extra_fields
