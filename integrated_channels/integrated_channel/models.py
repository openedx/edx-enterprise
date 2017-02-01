"""
Database models for Enterprise Integrated Channel.
"""
from __future__ import unicode_literals

from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _
from model_utils.models import TimeStampedModel


@python_2_unicode_compatible
class EnterpriseIntegratedChannel(TimeStampedModel):
    """
    Store information related to integrating with external enterprise systems.

    EnterpriseIntegratedChannel is an external system that the Enterprise Customer uses to manage enterprise
    related data. Each of these requires an edx plugin in order to send data to these systems, this model stores
    information related to what and where to send data from the enterprise app.
    """

    name = models.CharField(max_length=255, blank=False, null=False, help_text=_("Third Party name."))
    data_type = models.CharField(max_length=100, blank=False, null=False, help_text=_("Data Type"))

    class Meta:
        app_label = 'integrated_channel'
        verbose_name = _("Enterprise Integrated Channel")
        verbose_name_plural = _("Enterprise Integrated Channels")
        unique_together = (("name", "data_type"),)

    def __str__(self):
        """
        Return human-readable string representation.
        """
        return "<EnterpriseIntegratedChannel {name} for {data_type} data with id {id}>".format(
            name=self.name,
            data_type=self.data_type,
            id=self.id
        )

    def __repr__(self):
        """
        Return uniquely identifying string representation.
        """
        return self.__str__()


@python_2_unicode_compatible
class EnterpriseCustomerPluginConfiguration(TimeStampedModel):
    """
    Store information related to integrating with external systems for a particular enterprise customer.

    EnterpriseCustomerPluginConfiguration stores the relationship between EnterpriseCustomer
    and EnterpriseIntegratedChannel, representing which IntegratedChannels are configured for an Enterprise and
    what data to send where for a given Enterprise.
    """

    enterprise_customer_uuid = models.UUIDField()
    enterprise_integrated_channel = models.ForeignKey(EnterpriseIntegratedChannel, blank=False, null=False)
    active = models.BooleanField(blank=False, null=False)

    class Meta:
        app_label = 'integrated_channel'
        verbose_name = _("Enterprise Customer Plugin Configuration")
        verbose_name_plural = _("Enterprise Customer Plugin Configurations")
        unique_together = (("enterprise_customer_uuid", "enterprise_integrated_channel"),)

    def __str__(self):
        """
        Return human-readable string representation.
        """
        return "<EnterpriseCustomerPluginConfiguration for enterprise {enterprise} using channel {channel}>".format(
            enterprise=self.enterprise_customer_uuid,
            channel=self.enterprise_integrated_channel.name
        )

    def __repr__(self):
        """
        Return uniquely identifying string representation.
        """
        return self.__str__()
