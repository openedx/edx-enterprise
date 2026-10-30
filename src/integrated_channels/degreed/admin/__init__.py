"""
Django admin integration for configuring degreed app to communicate with Degreed systems.
"""

from config_models.admin import ConfigurationModelAdmin
from django_object_actions import DjangoObjectActions

from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect

from integrated_channels.degreed.models import (
    DegreedEnterpriseCustomerConfiguration,
    DegreedGlobalConfiguration,
    DegreedLearnerDataTransmissionAudit,
)
from integrated_channels.integrated_channel.admin import BaseLearnerDataTransmissionAuditAdmin


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


class DegreedEnterpriseCustomerConfigurationAdmin(DjangoObjectActions, admin.ModelAdmin):
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
    change_actions = ("force_content_metadata_transmission",)

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

    @admin.action(
        description="Force content metadata transmission for this Enterprise Customer"
    )
    def force_content_metadata_transmission(self, request, obj):
        """
        Updates the modified time of the customer record to retransmit courses metadata
        and redirects to configuration view with success or error message.
        """
        try:
            obj.enterprise_customer.save()
            messages.success(
                request,
                f'''The degreed enterprise customer content metadata
                “<DegreedEnterpriseCustomerConfiguration for Enterprise
                {obj.enterprise_customer.name}>” was updated successfully.''',
            )
        except ValidationError:
            messages.error(
                request,
                f'''The degreed enterprise customer content metadata
                “<DegreedEnterpriseCustomerConfiguration for Enterprise
                {obj.enterprise_customer.name}>” was not updated successfully.''',
            )
        return HttpResponseRedirect(
            "/admin/degreed/degreedenterprisecustomerconfiguration"
        )

    force_content_metadata_transmission.label = "Force content metadata transmission"


class DegreedLearnerDataTransmissionAuditAdmin(BaseLearnerDataTransmissionAuditAdmin):
    """
    Django admin model for DegreedLearnerDataTransmissionAudit.
    """
    list_display = (
        "enterprise_course_enrollment_id",
        "course_id",
        "status",
        "modified",
    )

    readonly_fields = (
        "degreed_user_email",
        "progress_status",
        "content_title",
        "enterprise_customer_name",
        "friendly_status_message",
        "api_record",
    )

    search_fields = (
        "degreed_user_email",
        "enterprise_course_enrollment_id",
        "course_id",
        "content_title",
        "friendly_status_message"
    )

    list_per_page = 1000

    class Meta:
        model = DegreedLearnerDataTransmissionAudit
