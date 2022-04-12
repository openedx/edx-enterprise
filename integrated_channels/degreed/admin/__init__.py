"""
Django admin integration for configuring degreed app to communicate with Degreed systems.
"""

from config_models.admin import ConfigurationModelAdmin

from django.contrib import admin

from integrated_channels.degreed.models import DegreedEnterpriseCustomerConfiguration, DegreedGlobalConfiguration


@admin.register(DegreedGlobalConfiguration)
class DegreedGlobalConfigurationAdmin(ConfigurationModelAdmin):
    """
    Django admin model for DegreedGlobalConfiguration.
    """

    list_display = (
        "completion_status_api_path",
        "course_api_path",
        "oauth_api_path",
    )

    class Meta:
        model = DegreedGlobalConfiguration


@admin.register(DegreedEnterpriseCustomerConfiguration)
class DegreedEnterpriseCustomerConfigurationAdmin(admin.ModelAdmin):
    """
    Django admin model for DegreedEnterpriseCustomerConfiguration.
    """

    list_display = (
        "enterprise_customer_name",
        "active",
        "key",
        "secret",
        "degreed_company_id",
        "degreed_base_url",
        "degreed_user_id",
        "degreed_user_password",
        "provider_id",
    )

    readonly_fields = (
        "enterprise_customer_name",
    )

    raw_id_fields = (
        "enterprise_customer",
    )

    list_filter = ("active",)
    search_fields = ("enterprise_customer_name",)

    class Meta:
        model = DegreedEnterpriseCustomerConfiguration

    def enterprise_customer_name(self, obj):
        """
        Returns: the name for the attached EnterpriseCustomer.

        Args:
            obj: The instance of DegreedEnterpriseCustomerConfiguration
                being rendered with this admin form.
        """
        return obj.enterprise_customer.name
