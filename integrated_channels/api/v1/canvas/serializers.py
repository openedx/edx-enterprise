"""
Serializers for Canvas.
"""
from rest_framework import serializers

from integrated_channels.canvas.models import CanvasEnterpriseCustomerConfiguration


class CanvasEnterpriseCustomerConfigurationSerializer(serializers.ModelSerializer):
    is_valid = serializers.ReadOnlyField()
    channel_code = serializers.ReadOnlyField()

    class Meta:
        model = CanvasEnterpriseCustomerConfiguration
        fields = '__all__'
