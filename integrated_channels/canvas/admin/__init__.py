"""
Admin integration for configuring Canvas app to communicate with Canvas systems.
"""

from django.contrib import admin

from integrated_channels.canvas.models import CanvasEnterpriseCustomerConfiguration


@admin.register(CanvasEnterpriseCustomerConfiguration)
class CanvasEnterpriseCustomerConfigurationAdmin(admin.ModelAdmin):
    """
    Django admin model for CanvasEnterpriseCustomerConfiguration.
    """
    list_display = (
        "enterprise_customer_name",
        "client_id",
        "client_secret",
        "canvas_account_id",
        "canvas_base_url",
    )

    readonly_fields = (
        "enterprise_customer_name",
        "refresh_token",
    )

    search_fields = ("enterprise_customer_name",)

    class Meta:
        model = CanvasEnterpriseCustomerConfiguration

    def enterprise_customer_name(self, obj):
        """
        Returns: the name for the attached EnterpriseCustomer.

        Args:
            obj: The instance of CanvasEnterpriseCustomerConfiguration
                being rendered with this admin form.
        """
        return obj.enterprise_customer.name
