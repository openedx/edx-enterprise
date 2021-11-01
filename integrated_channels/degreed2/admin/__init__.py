# -*- coding: utf-8 -*-
"""
Django admin integration for configuring degreed app to communicate with Degreed systems.
"""

from django.contrib import admin

from integrated_channels.degreed2.models import Degreed2EnterpriseCustomerConfiguration


@admin.register(Degreed2EnterpriseCustomerConfiguration)
class Degreed2EnterpriseCustomerConfigurationAdmin(admin.ModelAdmin):
    """
    Django admin model for Degreed2EnterpriseCustomerConfiguration.
    """

    list_display = (
        "enterprise_customer_name",
        "active",
        "client_id",
        "client_secret",
        "degreed_base_url",
        "degreed_token_fetch_base_url",
    )

    readonly_fields = (
        "enterprise_customer_name",
    )

    list_filter = ("active",)
    search_fields = ("enterprise_customer_name",)

    class Meta:
        model = Degreed2EnterpriseCustomerConfiguration

    def enterprise_customer_name(self, obj):
        """
        Returns: the name for the attached EnterpriseCustomer.

        Args:
            obj: The instance of Degreed2EnterpriseCustomerConfiguration
                being rendered with this admin form.
        """
        return obj.enterprise_customer.name
