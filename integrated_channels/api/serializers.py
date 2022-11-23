"""
Serializer for integrated channel api.
"""

from rest_framework import serializers

from integrated_channels.integrated_channel.models import EnterpriseCustomerPluginConfiguration


class EnterpriseCustomerPluginConfigSerializer(serializers.ModelSerializer):
    """
    Serializer for EnterpriseCustomerPluginConfiguration model
    """
    last_sync_attempted_at = serializers.SerializerMethodField()
    last_content_sync_attempted_at = serializers.SerializerMethodField()
    last_learner_sync_attempted_at = serializers.SerializerMethodField()
    last_sync_errored_at = serializers.SerializerMethodField()
    last_content_sync_errored_at = serializers.SerializerMethodField()
    last_learner_sync_errored_at = serializers.SerializerMethodField()

    class Meta:
        model = EnterpriseCustomerPluginConfiguration
        fields = (
            'id',
            'display_name',
            'enterprise_customer',
            'idp_id',
            'active',
            'last_sync_attempted_at',
            'last_content_sync_attempted_at',
            'last_learner_sync_attempted_at',
            'last_sync_errored_at',
            'last_content_sync_errored_at',
            'last_learner_sync_errored_at',
        )

    def get_last_sync_attempted_at(self, obj):
        """
        Return the most recent sync attempt date.
        """
        return obj.get_last_sync(False)

    def get_last_content_sync_attempted_at(self, obj):
        """
        Return the most recent content metadata item transmission sync attempt date.
        """
        return obj.get_last_content(False)

    def get_last_learner_sync_attempted_at(self, obj):
        """
        Return the most recent learner data transmission audit sync attempt date.
        """
        return obj.get_last_learner(False)

    def get_last_sync_errored_at(self, obj):
        """
        Return the most recent error transmission.
        """
        return obj.get_last_sync(True)

    def get_last_content_sync_errored_at(self, obj):
        """
        Return the most recent content metadata error transmission.
        """
        return obj.get_last_content(True)

    def get_last_learner_sync_errored_at(self, obj):
        """
        Return the most recent learner data error transmission.
        """
        return obj.get_last_learner(True)
