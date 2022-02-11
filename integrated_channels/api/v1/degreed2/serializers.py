"""
Serializer for Degreed2 configuration.
"""
from rest_framework import serializers

from integrated_channels.degreed2.models import Degreed2EnterpriseCustomerConfiguration


class Degreed2ConfigSerializer(serializers.ModelSerializer):
    is_valid = serializers.ReadOnlyField()
    channel_code = serializers.ReadOnlyField()

    class Meta:
        model = Degreed2EnterpriseCustomerConfiguration
        fields = '__all__'
