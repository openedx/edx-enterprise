"""
    Serializer for Moodle configuration.
"""
from rest_framework import serializers

from integrated_channels.api.serializers import EnterpriseCustomerPluginConfigSerializer
from integrated_channels.moodle.models import MoodleEnterpriseCustomerConfiguration


class MoodleConfigSerializer(EnterpriseCustomerPluginConfigSerializer):
    class Meta:
        model = MoodleEnterpriseCustomerConfiguration
        extra_fields = (
            'moodle_base_url',
            'service_short_name',
            'category_id',
            'encrypted_username',
            'encrypted_password',
            'encrypted_token',
        )
        fields = EnterpriseCustomerPluginConfigSerializer.Meta.fields + extra_fields

    encrypted_password = serializers.CharField(required=False, allow_blank=False, read_only=False)
    encrypted_username = serializers.CharField(required=False, allow_blank=False, read_only=False)
    encrypted_token = serializers.CharField(required=False, allow_blank=False, read_only=False)
