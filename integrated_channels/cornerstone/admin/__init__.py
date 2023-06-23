"""
Django admin integration for configuring cornerstone ondemand app to communicate with CSOD systems.
"""

from config_models.admin import ConfigurationModelAdmin

from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect
from django_object_actions import DjangoObjectActions

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
    change_actions = ("update_modified_time",)

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

    def update_modified_time(self, request, obj):
        """
        Updates the modified time of the customer record to retransmit courses metadata
        and redirects to configuration view with success or error message.
        """
        try:
            obj.enterprise_customer.save()
            messages.success(
                request,
                "The cornerstone enterprise customer modified time "
                "“<CornerstoneEnterpriseCustomerConfiguration for Enterprise {enterprise_name}>” "
                "was saved successfully.".format(
                    enterprise_name=obj.enterprise_customer.name
                ),
            )
        except ValidationError:
            messages.error(
                request,
                "The cornerstone enterprise customer modified time "
                "“<CornerstoneEnterpriseCustomerConfiguration for Enterprise {enterprise_name}>” "
                "was not saved successfully.".format(
                    enterprise_name=obj.enterprise_customer.name
                ),
            )
        return HttpResponseRedirect(
            "/admin/cornerstone/cornerstoneenterprisecustomerconfiguration"
        )
    update_modified_time.label = "Update Customer Modified Time"
    update_modified_time.short_description = (
        "Update modified time for this Enterprise Customer "
    )
    "to retransmit courses metadata"


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
