"""
Django admin integration for configuring sap_success_factors app to communicate with SAP SuccessFactors systems.
"""
from __future__ import absolute_import, unicode_literals

from django.contrib import admin
from config_models.admin import ConfigurationModelAdmin

from integrated_channels.sap_success_factors.models import (
    SAPSuccessFactorsEnterpriseCustomerConfiguration, SAPSuccessFactorsGlobalConfiguration
)


@admin.register(SAPSuccessFactorsGlobalConfiguration)
class SAPSuccessFactorsGlobalConfigurationAdmin(ConfigurationModelAdmin):
    """
    Django admin model for SAPSuccessFactorsGlobalConfiguration.
    """
    list_display = (
        "completion_status_api_path",
        "course_api_path",
        "oauth_api_path",
        "provider_id",
    )

    class Meta(object):
        model = SAPSuccessFactorsGlobalConfiguration


@admin.register(SAPSuccessFactorsEnterpriseCustomerConfiguration)
class SAPSuccessFactorsEnterpriseCustomerConfigurationAdmin(admin.ModelAdmin):
    """
    Django admin model for SAPSuccessFactorsEnterpriseCustomerConfiguration.
    """
    list_display = (
        "enterprise_customer_name",
        "active",
        "sapsf_base_url",
        "key",
    )

    readonly_fields = (
        "enterprise_customer_name",
    )

    list_filter = ("active",)
    search_fields = ("enterprise_customer_name",)

    class Meta(object):
        model = SAPSuccessFactorsEnterpriseCustomerConfiguration

    def enterprise_customer_name(self, obj):
        """
        Returns: the name for the attached EnterpriseCustomer, or the uuid if the EnterpriseCustomer does not exist.

        Args:
            obj: The instance of SAPSuccessFactorsEnterpriseCustomerConfiguration
                being rendered with this admin form.
        """
        return obj.enterprise_customer.name
