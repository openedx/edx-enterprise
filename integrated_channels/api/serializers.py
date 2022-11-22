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

    # TODO: only returning content sync times because learner audits have string representations
    # of timstamps (werid), and cannot be compared to a datetime with an associated timezone.
    # We're going to need to do additional work to change this and backfill those changes that
    # is not included in the scope of this ticket

    def get_last_sync_attempted_at(self, obj):
        """
        Return the most recent sync attempt date.
        """
        # return obj.get_last_sync(False, obj.id)
        return obj.get_last_content(False, obj.id)

    def get_last_content_sync_attempted_at(self, obj):
        """
        Return the most recent content metadata item transmission sync attempt date.
        """
        return obj.get_last_content(False, obj.id)

    def get_last_learner_sync_attempted_at(self, obj):
        """
        Return the most recent learner data transmission audit sync attempt date.
        """
        # return obj.get_last_learner(False, obj.id)
        return None

    def get_last_sync_errored_at(self, obj):
        """
        Return the most recent error transmission.
        """
        # return obj.get_last_sync(True, obj.id)
        return obj.get_last_content(True, obj.id)

    def get_last_content_sync_errored_at(self, obj):
        """
        Return the most recent content metadata error transmission.
        """
        print(obj)
        return obj.get_last_content(True, obj.id)

    def get_last_learner_sync_errored_at(self, obj):
        """
        Return the most recent learner data error transmission.
        """
        # return obj.get_last_learner(True, obj.id)
        return None
