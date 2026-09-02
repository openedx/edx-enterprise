"""
    Serializer for Moodle configuration.
"""
from rest_framework import serializers

from integrated_channels.api.serializers import EnterpriseCustomerPluginConfigSerializer
from integrated_channels.moodle.models import MoodleEnterpriseCustomerConfiguration


class MoodleConfigSerializer(EnterpriseCustomerPluginConfigSerializer):
    """
    Serializer for Moodle Enterprise Customer Configuration.
    Handles token or username/password authentication methods.
    """
    class Meta:
        model = MoodleEnterpriseCustomerConfiguration
        extra_fields = (
            'moodle_base_url',
            'service_short_name',
            'category_id',
            'username',
            'password',
            'token',
        )
        fields = EnterpriseCustomerPluginConfigSerializer.Meta.fields + extra_fields

    username = serializers.CharField(required=False, allow_blank=True, write_only=True)
    password = serializers.CharField(required=False, allow_blank=True, write_only=True)
    token = serializers.CharField(required=False, allow_blank=True, write_only=True)

    def _handle_credentials(self, instance, username=None, password=None, token=None):
        """Helper method to handle credential updates."""
        if token is not None:
            instance.decrypted_token = token
            instance.decrypted_username = None
            instance.decrypted_password = None
        elif username is not None and password is not None:
            instance.decrypted_token = None
            instance.decrypted_username = username
            instance.decrypted_password = password

    def create(self, validated_data):
        username = validated_data.pop('username', None)
        password = validated_data.pop('password', None)
        token = validated_data.pop('token', None)

        instance = super().create(validated_data)
        self._handle_credentials(instance, username, password, token)
        instance.save()
        return instance

    def update(self, instance, validated_data):
        username = validated_data.pop('username', None)
        password = validated_data.pop('password', None)
        token = validated_data.pop('token', None)

        instance = super().update(instance, validated_data)
        self._handle_credentials(instance, username, password, token)
        instance.save()
        return instance
