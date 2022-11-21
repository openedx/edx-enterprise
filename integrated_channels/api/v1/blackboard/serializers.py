"""
    Serializer for Blackboard configuration.
"""
from rest_framework import serializers

from integrated_channels.api.serializers import EnterpriseCustomerPluginConfigSerializer
from integrated_channels.blackboard.models import (
    BlackboardEnterpriseCustomerConfiguration,
    BlackboardGlobalConfiguration,
)


class BlackboardConfigSerializer(EnterpriseCustomerPluginConfigSerializer):
    oauth_authorization_url = serializers.ReadOnlyField()
    is_valid = serializers.ReadOnlyField()
    channel_code = serializers.ReadOnlyField()
    last_sync_attemped_at = serializers.ReadOnlyField()
    last_content_sync_attempted_at  = serializers.ReadOnlyField()
    last_learner_sync_attempted_at = serializers.ReadOnlyField()
    last_sync_errored_at = serializers.ReadOnlyField()
    last_content_sync_errored_at = serializers.ReadOnlyField()
    last_learner_sync_errored_at = serializers.ReadOnlyField()

    def get_last_sync_attemped_at(self, obj):
        """
        Return the most recent sync attempt date.
        """
        return obj.get_last_sync_attemped_at()

    def get_last_content_sync_attempted_at(self, obj):
        """
        Return the most recent content metadata item transmission sync attempt date.
        """
        return obj.get_recent_content_sync(obj, False)

    def get_last_learner_sync_attempted_at(self, obj):
        """
        Return the most recent learner data transmission audit sync attempt date.
        """
        return obj.get_last_learner_synced_at()

    def get_last_sync_errored_at(self, obj):
        """
        Return the most recent error transmission.
        """
        return max(
            obj.get_recent_content_sync(obj, True),
            obj.get_recent_learner_sync(obj, True)
        )

    def get_last_content_sync_errored_at(self, obj):
        """
        Return the most recent content metadata error transmission.
        """
        return obj.get_recent_content_sync(obj, True)

    def get_last_learner_sync_errored_at(self, obj):
        """
        Return the most recent learner data error transmission.
        """
        return obj.get_recent_content_sync(obj, False)


    class Meta(EnterpriseCustomerPluginConfigSerializer.Meta):
        # model = BlackboardEnterpriseCustomerConfiguration
        # fields = ('client_id', 'client_secret', 'blackboard_base_url',
        #           'refresh_token', 'transmission_chunk_size', 'uuid',
        #           'oauth_authorization_url', 'is_valid', 'channel_code',
        #           'last_sync_attemped_at', 'last_content_sync_attempted_at',
        #           'last_learner_sync_attempted_at', 'last_sync_errored_at',
        #           'last_content_sync_errored_at', 'last_learner_sync_errored_at')
        # depth = 1
        # # read_only_fields = ('last_sync_attemped_at', 'last_content_sync_attempted_at',
        # #                     'last_learner_sync_attempted_at', 'last_sync_errored_at',
        # #                     'last_content_sync_errored_at', 'last_learner_sync_errored_at')
        

        extra_fields = ('client_id', 'client_secret', 'blackboard_base_url',
                        'refresh_token', 'transmission_chunk_size', 'uuid',
                        'oauth_authorization_url', 'is_valid', 'channel_code')
        model = BlackboardEnterpriseCustomerConfiguration
        fields = EnterpriseCustomerPluginConfigSerializer.Meta.fields + extra_fields



class BlackboardGlobalConfigSerializer(serializers.ModelSerializer):

    class Meta:
        model = BlackboardGlobalConfiguration
        fields = ('app_key',)
