"""
Django admin integration for configuring sap_success_factors app to communicate with SAP SuccessFactors systems.
"""

from config_models.admin import ConfigurationModelAdmin
from requests import RequestException

from django.contrib import admin

from integrated_channels.exceptions import ClientError
from integrated_channels.sap_success_factors.client import SAPSuccessFactorsAPIClient
from integrated_channels.sap_success_factors.models import (
    SAPSuccessFactorsEnterpriseCustomerConfiguration,
    SAPSuccessFactorsGlobalConfiguration,
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
        "search_student_api_path",
    )

    class Meta:
        model = SAPSuccessFactorsGlobalConfiguration


@admin.register(SAPSuccessFactorsEnterpriseCustomerConfiguration)
class SAPSuccessFactorsEnterpriseCustomerConfigurationAdmin(admin.ModelAdmin):
    """
    Django admin model for SAPSuccessFactorsEnterpriseCustomerConfiguration.
    """
    fields = (
        'enterprise_customer',
        'idp_id',
        'active',
        'sapsf_base_url',
        'sapsf_company_id',
        'key',
        'secret',
        'sapsf_user_id',
        'user_type',
        'has_access_token',
        'prevent_self_submit_grades',
        'show_course_price',
        'disable_learner_data_transmissions',
        'transmit_total_hours',
        'transmission_chunk_size',
        'additional_locales',
        'catalogs_to_transmit',
    )

    list_display = (
        'enterprise_customer_name',
        'active',
        'sapsf_base_url',
        'modified',
    )
    ordering = ('enterprise_customer__name',)

    readonly_fields = (
        'has_access_token',
        'transmission_chunk_size',
    )

    list_filter = ('active',)
    search_fields = ('enterprise_customer__name',)

    class Meta:
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
                obj.user_type,
                obj.enterprise_customer.uuid
            )
        except (RequestException, ClientError):
            return False
        return bool(access_token and expires_at)

    has_access_token.boolean = True
    has_access_token.short_description = 'Has Access Token?'
