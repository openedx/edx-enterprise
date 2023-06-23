"""
Admin integration for configuring Canvas app to communicate with Canvas systems.
"""
from django_object_actions import DjangoObjectActions

from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect
from django.utils.html import format_html

from integrated_channels.canvas.models import CanvasEnterpriseCustomerConfiguration, CanvasLearnerDataTransmissionAudit
from integrated_channels.integrated_channel.admin import BaseLearnerDataTransmissionAuditAdmin


@admin.register(CanvasEnterpriseCustomerConfiguration)
class CanvasEnterpriseCustomerConfigurationAdmin(DjangoObjectActions, admin.ModelAdmin):
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
        "customer_oauth_authorization_url",
        "uuid",
        "transmission_chunk_size",
    )

    raw_id_fields = (
        "enterprise_customer",
    )

    search_fields = ("enterprise_customer_name",)
    change_actions = ("update_modified_time",)

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

    def customer_oauth_authorization_url(self, obj):
        """
        Returns: an html formatted oauth authorization link when the canvas_base_url and client_id are available.

        Args:
            obj: The instance of CanvasEnterpriseCustomerConfiguration
                being rendered with this admin form.
        """
        if obj.oauth_authorization_url:
            return format_html((f'<a href="{obj.oauth_authorization_url}">Authorize Link</a>'))
        else:
            return None

    def update_modified_time(self, request, obj):
        """
        Updates the modified time of the customer record to retransmit courses metadata
        and redirects to configuration view with success or error message.
        """
        try:
            obj.enterprise_customer.save()
            messages.success(
                request,
                "The canvas enterprise customer modified time "
                "“<CanvasEnterpriseCustomerConfiguration for Enterprise {enterprise_name}>” "
                "was saved successfully.".format(
                    enterprise_name=obj.enterprise_customer.name
                ),
            )
        except ValidationError:
            messages.error(
                request,
                "The canvas enterprise customer modified time "
                "“<CanvasEnterpriseCustomerConfiguration for Enterprise {enterprise_name}>” "
                "was not saved successfully.".format(
                    enterprise_name=obj.enterprise_customer.name
                ),
            )
        return HttpResponseRedirect(
            "/admin/canvas/canvasenterprisecustomerconfiguration"
        )
    update_modified_time.label = "Update Customer Modified Time"
    update_modified_time.short_description = (
        "Update modified time for this Enterprise Customer "
    )
    "to retransmit courses metadata"


@admin.register(CanvasLearnerDataTransmissionAudit)
class CanvasLearnerDataTransmissionAuditAdmin(BaseLearnerDataTransmissionAuditAdmin):
    """
    Django admin model for CanvasLearnerDataTransmissionAudit.
    """
    list_display = (
        "enterprise_course_enrollment_id",
        "course_id",
        "status",
        "modified",
    )

    readonly_fields = (
        "canvas_user_email",
        "progress_status",
        "content_title",
        "enterprise_customer_name",
        "friendly_status_message",
    )

    list_per_page = 1000

    class Meta:
        model = CanvasLearnerDataTransmissionAudit
