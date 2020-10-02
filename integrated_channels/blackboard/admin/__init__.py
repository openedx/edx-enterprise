"""
Admin integration for configuring Blackboard app to communicate with Blackboard systems.
"""

from django.contrib import admin

from integrated_channels.blackboard.models import BlackboardEnterpriseCustomerConfiguration


@admin.register(BlackboardEnterpriseCustomerConfiguration)
class BlackboardEnterpriseCustomerConfigurationAdmin(admin.ModelAdmin):
    """
    Django admin model for BlackEnterpriseCustomerConfiguration.
    """
    list_display = (
        "enterprise_customer_name",
        "client_id",
        "client_secret",
        "blackboard_base_url",
    )

    readonly_fields = (
        "enterprise_customer_name",
        "refresh_token",
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
