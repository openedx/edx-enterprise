"""
Admin integration for configuring Canvas app to communicate with Canvas systems.
"""

from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django_object_actions import DjangoObjectActions
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

    change_actions = ('retransmit_courses_metadata',)

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

    def retransmit_courses_metadata(self, request, obj):
        """
        Updates the modified time of the customer record to re-sync courses metadata
        and redirects to configuration view with success or error message.
        """
        try: 
            obj.enterprise_customer.save()
            messages.success(
                request,
                'The canvas enterprise customer courses metadata '
                '“<CanvasEnterpriseCustomerConfiguration for Enterprise {enterprise_name}>” '
                'was retransmitted successfully.'.format(enterprise_name=obj.enterprise_customer.name))
        except:
            messages.error(
                request,
                'The canvas enterprise customer courses metadata '
                '“<CanvasEnterpriseCustomerConfiguration for Enterprise {enterprise_name}>” '
                'was not retransmitted successfully.'.format(enterprise_name=obj.enterprise_customer.name))
        return HttpResponseRedirect('/admin/canvas/canvasenterprisecustomerconfiguration')
    retransmit_courses_metadata.label = 'Retransmit Courses Metadata'
    retransmit_courses_metadata.short_description = 'Retransmit courses metadata for this Enterprise Customer'


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
