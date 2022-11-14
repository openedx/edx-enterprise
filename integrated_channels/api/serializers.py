"""
Serializer for integrated channel api.
"""

from logging import getLogger
from rest_framework import serializers
from integrated_channels.integrated_channel.models import EnterpriseCustomerPluginConfiguration

from integrated_channels.utils import get_recent_content_sync, get_recent_learner_sync

LOGGER = getLogger(__name__)


class EnterpriseCustomerPluginConfigSerializer(serializers.ModelSerializer):
    """
    Serializer for EnterpriseCustomerPluginConfiguration model
    """

    class Meta:
        model = EnterpriseCustomerPluginConfiguration
        fields = (
            'id',
            'display_name',
            'enterprise_customer',
            'idp_id',
            'active',
            'last_sync_attemped_at',
            'last_content_sync_attempted_at',
            'last_learner_sync_attempted_at',
            'last_sync_errored_at',
            'last_content_sync_errored_at',
            'last_learner_sync_errored_at',
        )

        last_sync_attemped_at = serializers.SerializerMethodField()
        last_content_sync_attempted_at = serializers.SerializerMethodField()
        last_learner_sync_attempted_at = serializers.SerializerMethodField()
        last_sync_errored_at = serializers.SerializerMethodField()
        last_content_sync_errored_at = serializers.SerializerMethodField()
        last_learner_sync_errored_at = serializers.SerializerMethodField()

        def get_last_sync_attemped_at(self, obj):
            """
            Return the most recent sync attempt date.
            """
            return max(
                get_recent_content_sync(obj, False),
                get_recent_learner_sync(obj, False)
            )

        def get_last_content_sync_attempted_at(self, obj):
            """
            Return the most recent content metadata item transmission sync attempt date.
            """
            return get_recent_content_sync(obj, False)

        def get_last_learner_sync_attempted_at(self, obj):
            """
            Return the most recent learner data transmission audit sync attempt date.
            """
            return get_recent_learner_sync(obj, False)

        def get_last_sync_errored_at(self, obj):
            """
            Return the most recent error transmission.
            """
            return max(
                get_recent_content_sync(obj, True),
                get_recent_learner_sync(obj, True)
            )

        def get_last_content_sync_errored_at(self, obj):
            """
            Return the most recent content metadata error transmission.
            """
            return get_recent_content_sync(obj, True)

        def get_last_learner_sync_errored_at(self, obj):
            """
            Return the most recent learner data error transmission.
            """
            return get_recent_content_sync(obj, False)
