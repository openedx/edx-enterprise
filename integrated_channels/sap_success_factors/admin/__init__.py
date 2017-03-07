"""
Django admin integration for configuring sap_success_factors app to communicate with SAP SuccessFactors systems.
"""
from __future__ import absolute_import, unicode_literals

from django.contrib import admin
from config_models.admin import ConfigurationModelAdmin
from requests import RequestException

from integrated_channels.sap_success_factors.models import (
    SAPSuccessFactorsEnterpriseCustomerConfiguration, SAPSuccessFactorsGlobalConfiguration
)
from integrated_channels.sap_success_factors.client import SAPSuccessFactorsAPIClient


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
        "secret",
        "sapsf_company_id",
        "sapsf_user_id",
        "has_access_token",
    )

    readonly_fields = (
        "enterprise_customer_name",
        "has_access_token",
    )

    list_filter = ("active",)
    search_fields = ("enterprise_customer_name",)

    class Meta(object):
        model = SAPSuccessFactorsEnterpriseCustomerConfiguration

    def enterprise_customer_name(self, obj):
        """
        Returns: the name for the attached EnterpriseCustomer.

        Args:
            obj: The instance of SAPSuccessFactorsEnterpriseCustomerConfiguration
                being rendered with this admin form.
        """
        return obj.enterprise_customer.name

    def has_access_token(self, obj):
        """
        Confirms the presence and validity of the access token for the SAP SuccessFactors client instance

        Returns: a bool value indicating the presence of the access token

        Args:
            obj: The instance of SAPSuccessFactorsEnterpriseCustomerConfiguration
                being rendered with this admin form.
        """
        try:
            access_token, expires_at = SAPSuccessFactorsAPIClient.get_oauth_access_token(
                obj.sapsf_base_url,
                obj.key,
                obj.secret,
                obj.sapsf_company_id,
                obj.sapsf_user_id,
                obj.user_type
            )
        except (RequestException, ValueError):
            return False
        return bool(access_token and expires_at)

    has_access_token.boolean = True
