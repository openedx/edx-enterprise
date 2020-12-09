"""
    Serializer for Moodle configuration.
"""
from rest_framework import serializers

from integrated_channels.moodle.models import MoodleEnterpriseCustomerConfiguration


class MoodleConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = MoodleEnterpriseCustomerConfiguration
        fields = '__all__'
