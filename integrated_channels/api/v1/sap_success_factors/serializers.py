"""
    Serializer for Success Factors configuration.
"""
from rest_framework import serializers

from integrated_channels.sap_success_factors.models import SAPSuccessFactorsEnterpriseCustomerConfiguration


class SAPSuccessFactorsConfigSerializer(serializers.ModelSerializer):
    is_valid = serializers.ReadOnlyField()
    channel_code = serializers.ReadOnlyField()

    class Meta:
        model = SAPSuccessFactorsEnterpriseCustomerConfiguration
        fields = '__all__'
