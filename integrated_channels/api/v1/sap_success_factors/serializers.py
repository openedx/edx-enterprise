"""
    Serializer for Success Factors configuration.
"""
from rest_framework import serializers

from integrated_channels.api.serializers import EnterpriseCustomerPluginConfigSerializer
from integrated_channels.sap_success_factors.models import SAPSuccessFactorsEnterpriseCustomerConfiguration


class SAPSuccessFactorsConfigSerializer(EnterpriseCustomerPluginConfigSerializer):
    is_valid = serializers.ReadOnlyField()
    channel_code = serializers.ReadOnlyField()
    last_sync_attempted_at = serializers.SerializerMethodField()
    last_content_sync_attempted_at = serializers.SerializerMethodField()
    last_learner_sync_attempted_at = serializers.SerializerMethodField()
    last_sync_errored_at = serializers.SerializerMethodField()
    last_content_sync_errored_at = serializers.SerializerMethodField()
    last_learner_sync_errored_at = serializers.SerializerMethodField()

    class Meta:
        model = SAPSuccessFactorsEnterpriseCustomerConfiguration
        fields = ('id', 'key', 'sapsf_base_url', 'sapsf_company_id', 'sapsf_user_id',
                  'secret', 'user_type', 'additional_locales', 'show_course_price',
                  'transmit_total_hours', 'prevent_self_submit_grades', 'enterprise_customer',
                  'transmission_chunk_size', 'is_valid', 'channel_code', 'last_sync_attempted_at',
                  'last_content_sync_attempted_at', 'last_learner_sync_attempted_at',
                  'last_sync_errored_at', 'last_content_sync_errored_at', 'last_learner_sync_errored_at')
