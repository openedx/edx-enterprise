# -*- coding: utf-8 -*-
"""
Database models for Enterprise Integrated Channel Blackboard.
"""

from simple_history.models import HistoricalRecords

from django.db import models
from django.utils.encoding import python_2_unicode_compatible

from integrated_channels.integrated_channel.models import EnterpriseCustomerPluginConfiguration

from .exporters.content_metadata import BlackboardContentMetadataExporter
from .transmitters.content_metadata import BlackboardContentMetadataTransmitter


@python_2_unicode_compatible
class BlackboardEnterpriseCustomerConfiguration(EnterpriseCustomerPluginConfiguration):
    """
    The Enterprise-specific configuration we need for integrating with Blackboard.

    .. no_pii:
    """

    client_id = models.CharField(
        max_length=255,
        null=True,
        verbose_name="API Client ID or Blackboard Application Key",
        help_text=(
            "The API Client ID provided to edX by the enterprise customer to be used to make API "
            "calls on behalf of the customer. Called Application Key in Blackboard"
        )
    )

    client_secret = models.CharField(
        max_length=255,
        null=True,
        verbose_name="API Client Secret or Application Secret",
        help_text=(
            "The API Client Secret provided to edX by the enterprise customer to be used to make "
            " API calls on behalf of the customer. Called Application Secret in Blackboard"
        )
    )

    blackboard_base_url = models.CharField(
        max_length=255,
        null=True,
        verbose_name="Base URL",
        help_text="The base URL used for API requests to Blackboard, i.e. https://blackboard.com."
    )

    refresh_token = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Oauth2 Refresh Token",
        help_text="The refresh token provided by Blackboard along with the access token request,"
                  "used to re-request the access tokens over multiple client sessions."
    )

    history = HistoricalRecords()

    class Meta:
        app_label = 'blackboard'

    def __str__(self):
        """
        Return human-readable string representation.
        """
        return "<BlackboardEnterpriseCustomerConfiguration for Enterprise {enterprise_name}>".format(
            enterprise_name=self.enterprise_customer.name
        )

    def __repr__(self):
        """
        Return uniquely identifying string representation.
        """
        return self.__str__()

    @staticmethod
    def channel_code():
        """
        Returns an capitalized identifier for this channel class, unique among subclasses.
        """
        return 'BLACKBOARD'

    def get_content_metadata_exporter(self, user):
        return BlackboardContentMetadataExporter(user, self)

    def get_content_metadata_transmitter(self):
        return BlackboardContentMetadataTransmitter(self)
