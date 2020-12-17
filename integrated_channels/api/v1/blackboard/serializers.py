"""
    Serializer for Blackboard configuration.
"""
from rest_framework import serializers

from integrated_channels.blackboard.models import BlackboardEnterpriseCustomerConfiguration


class BlackboardConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlackboardEnterpriseCustomerConfiguration
        fields = '__all__'
