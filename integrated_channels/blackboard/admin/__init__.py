"""
Admin integration for configuring Blackboard app to communicate with Blackboard systems.
"""
from config_models.admin import ConfigurationModelAdmin

from django.contrib import admin
from django.utils.html import format_html

from integrated_channels.blackboard.models import (
    BlackboardEnterpriseCustomerConfiguration,
    BlackboardGlobalConfiguration,
)


@admin.register(BlackboardGlobalConfiguration)
class BlackboardGlobalConfigurationAdmin(ConfigurationModelAdmin):
    """
    Django admin model for BlackboardGlobalConfiguration.
    """
    list_display = (
        "app_key",
        "app_secret",
    )

    class Meta:
        model = BlackboardGlobalConfiguration


@admin.register(BlackboardEnterpriseCustomerConfiguration)
class BlackboardEnterpriseCustomerConfigurationAdmin(admin.ModelAdmin):
    """
    Django admin model for BlackEnterpriseCustomerConfiguration.
    """
    list_display = (
        "enterprise_customer_name",
        "blackboard_base_url",
    )

    readonly_fields = (
        "enterprise_customer_name",
        "refresh_token",
        "customer_oauth_authorization_url",
        "uuid",
        "transmission_chunk_size",
    )

    raw_id_fields = (
        "enterprise_customer",
    )

    search_fields = ("enterprise_customer_name",)

    class Meta:
        model = BlackboardEnterpriseCustomerConfiguration

    def enterprise_customer_name(self, obj):
        """
        Returns: the name for the attached EnterpriseCustomer.

        Args:
            obj: The instance of BlackboardEnterpriseCustomerConfiguration
                being rendered with this admin form.
        """
        return obj.enterprise_customer.name

    def customer_oauth_authorization_url(self, obj):
        """
        Returns: an html formatted oauth authorization link when the blackboard_base_url and client_id are available.

        Args:
            obj: The instance of BlackboardEnterpriseCustomerConfiguration
                being rendered with this admin form.
        """
        if obj.oauth_authorization_url:
            return format_html((f'<a href="{obj.oauth_authorization_url}">Authorize Link</a>'))
        else:
            return None
