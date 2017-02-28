"""
Django admin integration for integrated_channel app.
"""
from __future__ import absolute_import, unicode_literals

from django.contrib import admin

from integrated_channels.integrated_channel.models import (
    EnterpriseCustomerPluginConfiguration, EnterpriseIntegratedChannel
)


@admin.register(EnterpriseIntegratedChannel)
class EnterpriseIntegratedChannelAdmin(admin.ModelAdmin):
    """
    Django admin model for EnterpriseIntegratedChannel.
    """
    list_display = (
        "name",
        "data_type",
    )

    list_filter = ("data_type",)
    search_fields = ("name", "data_type",)

    class Meta(object):
        model = EnterpriseIntegratedChannel
