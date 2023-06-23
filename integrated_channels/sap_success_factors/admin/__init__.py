"""
Django admin integration for configuring sap_success_factors app to communicate with SAP SuccessFactors systems.
"""

from config_models.admin import ConfigurationModelAdmin
from django_object_actions import DjangoObjectActions
from requests import RequestException

from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect

from integrated_channels.exceptions import ClientError
from integrated_channels.integrated_channel.admin import BaseLearnerDataTransmissionAuditAdmin
from integrated_channels.sap_success_factors.client import SAPSuccessFactorsAPIClient
from integrated_channels.sap_success_factors.models import (
    SAPSuccessFactorsEnterpriseCustomerConfiguration,
    SAPSuccessFactorsGlobalConfiguration,
    SapSuccessFactorsLearnerDataTransmissionAudit,
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
class SAPSuccessFactorsEnterpriseCustomerConfigurationAdmin(DjangoObjectActions, admin.ModelAdmin):
    """
    Django admin model for SAPSuccessFactorsEnterpriseCustomerConfiguration.
    """
    fields = (
        "enterprise_customer",
        "idp_id",
        "active",
        "sapsf_base_url",
        "sapsf_company_id",
        "key",
        "secret",
        "sapsf_user_id",
        "user_type",
        "has_access_token",
        "prevent_self_submit_grades",
        "show_course_price",
        "disable_learner_data_transmissions",
        "transmit_total_hours",
        "transmission_chunk_size",
        "additional_locales",
        "catalogs_to_transmit",
        "display_name",
    )

    list_display = (
        "enterprise_customer_name",
        "active",
        "sapsf_base_url",
        "modified",
    )
    ordering = ("enterprise_customer__name",)

    readonly_fields = ("has_access_token",)

    raw_id_fields = ("enterprise_customer",)

    list_filter = ("active",)
    search_fields = ("enterprise_customer__name",)
    change_actions = ("update_modified_time",)

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
    has_access_token.short_description = "Has Access Token?"

    def update_modified_time(self, request, obj):
        """
        Updates the modified time of the customer record to retransmit courses metadata
        and redirects to configuration view with success or error message.
        """
        try:
            obj.enterprise_customer.save()
            messages.success(
                request,
                "The sap success factors enterprise customer modified time "
                "“<SAPSuccessFactorsEnterpriseCustomerConfiguration for Enterprise {enterprise_name}>” "
                "was saved successfully.".format(
                    enterprise_name=obj.enterprise_customer.name
                ),
            )
        except ValidationError:
            messages.error(
                request,
                "The sap success factors enterprise customer modified time "
                "“<SAPSuccessFactorsEnterpriseCustomerConfiguration for Enterprise {enterprise_name}>” "
                "was not saved successfully.".format(
                    enterprise_name=obj.enterprise_customer.name
                ),
            )
        return HttpResponseRedirect(
            "/admin/sap_success_factors/sapsuccessfactorsenterprisecustomerconfiguration"
        )
    update_modified_time.label = "Update Customer Modified Time"
    update_modified_time.short_description = (
        "Update modified time for this Enterprise Customer "
    )
    "to retransmit courses metadata"


@admin.register(SapSuccessFactorsLearnerDataTransmissionAudit)
class SapSuccessFactorsLearnerDataTransmissionAuditAdmin(
    BaseLearnerDataTransmissionAuditAdmin
):
    """
    Django admin model for SapSuccessFactorsLearnerDataTransmissionAudit.
    """

    list_display = (
        "enterprise_course_enrollment_id",
        "course_id",
        "status",
        "modified",
    )

    readonly_fields = (
        "sapsf_user_id",
        "progress_status",
        "content_title",
        "enterprise_customer_name",
        "friendly_status_message",
    )

    list_per_page = 1000

    class Meta:
        model = SapSuccessFactorsLearnerDataTransmissionAudit
