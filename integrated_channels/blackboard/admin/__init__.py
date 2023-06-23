"""
Admin integration for configuring Blackboard app to communicate with Blackboard systems.
"""
from config_models.admin import ConfigurationModelAdmin

from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django_object_actions import DjangoObjectActions
from django.utils.html import format_html
import inspect

from integrated_channels.blackboard.models import (
    BlackboardEnterpriseCustomerConfiguration,
    BlackboardGlobalConfiguration,
    BlackboardLearnerDataTransmissionAudit,
)
from integrated_channels.integrated_channel.admin import BaseLearnerDataTransmissionAuditAdmin


@admin.register(BlackboardGlobalConfiguration)
class BlackboardGlobalConfigurationAdmin(ConfigurationModelAdmin):
    """
    Django admin model for BlackboardGlobalConfiguration.
    """
    list_display = (
        "app_key",
        "app_secret",
    )

    class Meta:
        model = BlackboardGlobalConfiguration


@admin.register(BlackboardEnterpriseCustomerConfiguration)
class BlackboardEnterpriseCustomerConfigurationAdmin(DjangoObjectActions, admin.ModelAdmin):
    """
    Django admin model for BlackEnterpriseCustomerConfiguration.
    """
    list_display = (
        "enterprise_customer_name",
        "blackboard_base_url",
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
    change_actions = ('update_modified_time',)

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

    def customer_oauth_authorization_url(self, obj):
        """
        Returns: an html formatted oauth authorization link when the blackboard_base_url and client_id are available.

        Args:
            obj: The instance of BlackboardEnterpriseCustomerConfiguration
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
                'The blackboard enterprise customer modified time '
                '“<BlackboardEnterpriseCustomerConfiguration for Enterprise {enterprise_name}>” '
                'was saved successfully.'.format(enterprise_name=obj.enterprise_customer.name))
        except:
            messages.error(
                request,
                'The blackboard enterprise customer modified time '
                '“<BlackboardEnterpriseCustomerConfiguration for Enterprise {enterprise_name}>” '
                'was not saved successfully.'.format(enterprise_name=obj.enterprise_customer.name))
        return HttpResponseRedirect('/admin/blackboard/blackboardenterprisecustomerconfiguration')
    update_modified_time.label = 'Update Customer Modified Time'
    update_modified_time.short_description = 'Update modified time for this Enterprise Customer to retransmit courses metadata'


@admin.register(BlackboardLearnerDataTransmissionAudit)
class BlackboardLearnerDataTransmissionAuditAdmin(BaseLearnerDataTransmissionAuditAdmin):
    """
    Django admin model for BlackboardLearnerDataTransmissionAudit.
    """
    list_display = (
        "enterprise_course_enrollment_id",
        "course_id",
        "status",
        "modified",
    )

    readonly_fields = (
        "blackboard_user_email",
        "progress_status",
        "content_title",
        "enterprise_customer_name",
        "friendly_status_message",
    )

    list_per_page = 1000

    class Meta:
        model = BlackboardLearnerDataTransmissionAudit
