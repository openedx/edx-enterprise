"""
Django admin integration for configuring cornerstone ondemand app to communicate with CSOD systems.
"""

from config_models.admin import ConfigurationModelAdmin
from django_object_actions import DjangoObjectActions

from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect

from integrated_channels.cornerstone.models import (
    CornerstoneEnterpriseCustomerConfiguration,
    CornerstoneGlobalConfiguration,
    CornerstoneLearnerDataTransmissionAudit,
)
from integrated_channels.integrated_channel.admin import BaseLearnerDataTransmissionAuditAdmin


@admin.register(CornerstoneGlobalConfiguration)
class CornerstoneGlobalConfigurationAdmin(ConfigurationModelAdmin):
    """
    Django admin model for CornerstoneGlobalConfiguration.
    """

    list_display = (
        "completion_status_api_path",
        "key",
        "secret",
    )

    class Meta:
        model = CornerstoneGlobalConfiguration


@admin.register(CornerstoneEnterpriseCustomerConfiguration)
class CornerstoneEnterpriseCustomerConfigurationAdmin(DjangoObjectActions, admin.ModelAdmin):
    """
    Django admin model for CornerstoneEnterpriseCustomerConfiguration.
    """

    list_display = (
        "enterprise_customer_name",
        "active",
        "cornerstone_base_url",
    )

    readonly_fields = (
        "enterprise_customer_name",
        "session_token",
        "session_token_modified",
    )

    raw_id_fields = (
        "enterprise_customer",
    )

    list_filter = ("active",)
    search_fields = ("enterprise_customer_name",)
    change_actions = ("force_content_metadata_transmission",)

    class Meta:
        model = CornerstoneEnterpriseCustomerConfiguration

    def enterprise_customer_name(self, obj):
        """
        Returns: the name for the attached EnterpriseCustomer.

        Args:
            obj: The instance of CornerstoneEnterpriseCustomerConfiguration
                being rendered with this admin form.
        """
        return obj.enterprise_customer.name

    def force_content_metadata_transmission(self, request, obj):
        """
        Updates the modified time of the customer record to retransmit courses metadata
        and redirects to configuration view with success or error message.
        """
        try:
            obj.enterprise_customer.save()
            messages.success(
                request,
                f'''The cornerstone enterprise customer content metadata
                “<CornerstoneEnterpriseCustomerConfiguration for Enterprise
                {obj.enterprise_customer.name}>” was updated successfully.''',
            )
        except ValidationError:
            messages.error(
                request,
                f'''The cornerstone enterprise customer content metadata
                “<CornerstoneEnterpriseCustomerConfiguration for Enterprise
                {obj.enterprise_customer.name}>” was not updated successfully.''',
            )
        return HttpResponseRedirect(
            "/admin/cornerstone/cornerstoneenterprisecustomerconfiguration"
        )
    force_content_metadata_transmission.label = "Force content metadata transmission"
    force_content_metadata_transmission.short_description = (
        "Force content metadata transmission for this Enterprise Customer"
    )


@admin.register(CornerstoneLearnerDataTransmissionAudit)
class CornerstoneLearnerDataTransmissionAuditAdmin(BaseLearnerDataTransmissionAuditAdmin):
    """
    Django admin model for CornerstoneLearnerDataTransmissionAudit.
    """
    list_display = (
        "user_id",
        "enterprise_course_enrollment_id",
        "course_id",
        "status",
    )

    raw_id_fields = (
        "user",
    )

    readonly_fields = (
        "user_email",
        "progress_status",
        "content_title",
        "enterprise_customer_name",
        "friendly_status_message",
    )

    class Meta:
        model = CornerstoneLearnerDataTransmissionAudit

    def user_email(self, obj):
        """
        Returns: the name for the attached EnterpriseCustomer.

        Args:
            obj: The instance of CornerstoneLearnerDataTransmissionAudit
                being rendered with this admin form.
        """
        return obj.user.email
