"""
    Serializer for Success Factors configuration.
"""
from rest_framework import serializers

from integrated_channels.api.serializers import EnterpriseCustomerPluginConfigSerializer
from integrated_channels.sap_success_factors.models import SAPSuccessFactorsEnterpriseCustomerConfiguration


class SAPSuccessFactorsConfigSerializer(EnterpriseCustomerPluginConfigSerializer):
    class Meta:
        model = SAPSuccessFactorsEnterpriseCustomerConfiguration
        extra_fields = (
            'encrypted_key',
            'sapsf_base_url',
            'sapsf_company_id',
            'sapsf_user_id',
            'encrypted_secret',
            'user_type',
            'additional_locales',
            'show_course_price',
            'transmit_total_hours',
            'prevent_self_submit_grades',
        )
        fields = EnterpriseCustomerPluginConfigSerializer.Meta.fields + extra_fields

    encrypted_key = serializers.CharField(required=False, allow_blank=False, read_only=False)
    encrypted_secret = serializers.CharField(required=False, allow_blank=False, read_only=False)
