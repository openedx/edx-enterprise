# -*- coding: utf-8 -*-
"""
Database models for Enterprise Integrated Channel Canvas.
"""

from logging import getLogger

from config_models.models import ConfigurationModel
from simple_history.models import HistoricalRecords

from django.db import models
from django.utils.encoding import python_2_unicode_compatible

from integrated_channels.integrated_channel.models import EnterpriseCustomerPluginConfiguration

LOGGER = getLogger(__name__)


# pylint: disable=feature-toggle-needs-doc
@python_2_unicode_compatible
class CanvasGlobalConfiguration(ConfigurationModel):
    """
    The global configuration for integrating with Canvas.

    .. no_pii:
    """

    course_api_path = models.CharField(
        max_length=255,
        verbose_name="Course Metadata API Path",
        help_text="The API path for making course metadata POST/DELETE requests to Canvas."
    )

    class Meta:
        app_label = 'canvas'

    def __str__(self):
        """
        Return a human-readable string representation of the object.
        """
        return "<CanvasGlobalConfiguration with id {id}>".format(id=self.id)

    def __repr__(self):
        """
        Return uniquely identifying string representation.
        """
        return self.__str__()


@python_2_unicode_compatible
class CanvasEnterpriseCustomerConfiguration(EnterpriseCustomerPluginConfiguration):
    """
    The Enterprise-specific configuration we need for integrating with Canvas.

    Based on: https://canvas.instructure.com/doc/api/file.oauth.html#oauth2-flow-3

    .. no_pii:
    """

    client_id = models.CharField(
        max_length=255,
        null=True,
        verbose_name="API Client ID",
        help_text=(
            "The API Client ID provided to edX by the enterprise customer to be used to make API "
            "calls to Canvas on behalf of the customer."
        )
    )

    client_secret = models.CharField(
        max_length=255,
        null=True,
        verbose_name="API Client Secret",
        help_text=(
            "The API Client Secret provided to edX by the enterprise customer to be used to make "
            " API calls to Canvas on behalf of the customer."
        )
    )

    canvas_account_id = models.IntegerField(
        null=True,
        verbose_name="Canvas Account Number",
        help_text="Account number to use during api calls. Called account_id in canvas. "
                  " Required to create courses etc."
    )

    canvas_base_url = models.CharField(
        max_length=255,
        null=True,
        verbose_name="Canvas Base URL",
        help_text="The base URL used for API requests to Canvas, i.e. https://instructure.com."
    )

    history = HistoricalRecords()

    class Meta:
        app_label = 'canvas'

    def __str__(self):
        """
        Return human-readable string representation.
        """
        return "<CanvasEnterpriseCustomerConfiguration for Enterprise {enterprise_name}>".format(
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
        return 'CANVAS'
