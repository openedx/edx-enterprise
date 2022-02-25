"""
    Serializer for Cornerstone configuration.
"""
from rest_framework import serializers

from integrated_channels.cornerstone.models import CornerstoneEnterpriseCustomerConfiguration


class CornerstoneConfigSerializer(serializers.ModelSerializer):
    is_valid = serializers.ReadOnlyField()
    channel_code = serializers.ReadOnlyField()

    class Meta:
        model = CornerstoneEnterpriseCustomerConfiguration
        fields = '__all__'
