"""
Serializer for Degreed2 configuration.
"""
from rest_framework import serializers

from integrated_channels.degreed2.models import Degreed2EnterpriseCustomerConfiguration


class Degreed2ConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = Degreed2EnterpriseCustomerConfiguration
        fields = '__all__'
