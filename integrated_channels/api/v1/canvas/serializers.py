"""
Serializers for Canvas.
"""
from rest_framework import serializers

from integrated_channels.canvas.models import CanvasEnterpriseCustomerConfiguration


class CanvasEnterpriseCustomerConfigurationSerializer(serializers.ModelSerializer):
    class Meta:
        model = CanvasEnterpriseCustomerConfiguration
        fields = '__all__'
