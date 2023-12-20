"""
    Serializer for Moodle configuration.
"""
from integrated_channels.api.serializers import EnterpriseCustomerPluginConfigSerializer
from integrated_channels.moodle.models import MoodleEnterpriseCustomerConfiguration


class MoodleConfigSerializer(EnterpriseCustomerPluginConfigSerializer):
    class Meta:
        model = MoodleEnterpriseCustomerConfiguration
        extra_fields = (
            'moodle_base_url',
            'service_short_name',
            'category_id',
            'username',
            'password',
            'token',
        )
        fields = EnterpriseCustomerPluginConfigSerializer.Meta.fields + extra_fields
