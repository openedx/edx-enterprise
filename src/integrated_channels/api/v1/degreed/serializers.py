"""
    Serializer for Degreed configuration.
"""
from rest_framework import serializers

from integrated_channels.api.serializers import EnterpriseCustomerPluginConfigSerializer
from integrated_channels.degreed.models import DegreedEnterpriseCustomerConfiguration


class DegreedConfigSerializer(EnterpriseCustomerPluginConfigSerializer):
    class Meta:
        model = DegreedEnterpriseCustomerConfiguration
        extra_fields = (
            'key',
            'secret',
            'degreed_company_id',
            'degreed_base_url',
            'degreed_user_id',
            'degreed_user_password',
            'provider_id',
        )
        fields = EnterpriseCustomerPluginConfigSerializer.Meta.fields + extra_fields
