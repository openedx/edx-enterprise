# -*- coding: utf-8 -*-
"""
Django admin integration for configuring degreed app to communicate with Degreed systems.
"""

from django_object_actions import DjangoObjectActions

from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect

from integrated_channels.degreed2.models import (
    Degreed2EnterpriseCustomerConfiguration,
    Degreed2LearnerDataTransmissionAudit,
)
from integrated_channels.integrated_channel.admin import BaseLearnerDataTransmissionAuditAdmin


@admin.register(Degreed2EnterpriseCustomerConfiguration)
class Degreed2EnterpriseCustomerConfigurationAdmin(DjangoObjectActions, admin.ModelAdmin):
    """
    Django admin model for Degreed2EnterpriseCustomerConfiguration.
    """

    list_display = (
        "enterprise_customer_name",
        "active",
        "degreed_base_url",
        "degreed_token_fetch_base_url",
        "modified",
    )

    readonly_fields = (
        "enterprise_customer_name",
        "transmission_chunk_size",
    )

    raw_id_fields = (
        "enterprise_customer",
    )

    list_filter = ("active",)
    search_fields = ("enterprise_customer_name",)
    change_actions = ("update_modified_time",)

    class Meta:
        model = Degreed2EnterpriseCustomerConfiguration

    def enterprise_customer_name(self, obj):
        """
        Returns: the name for the attached EnterpriseCustomer.

        Args:
            obj: The instance of Degreed2EnterpriseCustomerConfiguration
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
                'The degreed2 enterprise customer modified time '
                '“<Degreed2EnterpriseCustomerConfiguration for Enterprise {enterprise_name}>” '
                'was saved successfully.'.format(enterprise_name=obj.enterprise_customer.name))
        except ValidationError:
            messages.error(
                request,
                'The degreed2 enterprise customer modified time '
                '“<Degreed2EnterpriseCustomerConfiguration for Enterprise {enterprise_name}>” '
                'was not saved successfully.'.format(enterprise_name=obj.enterprise_customer.name))
        return HttpResponseRedirect('/admin/degreed2/degreed2enterprisecustomerconfiguration')
    update_modified_time.label = "Update Customer Modified Time"
    update_modified_time.short_description = (
        "Update modified time for this Enterprise Customer "
    )
    "to retransmit courses metadata"


@admin.register(Degreed2LearnerDataTransmissionAudit)
class Degreed2LearnerDataTransmissionAuditAdmin(BaseLearnerDataTransmissionAuditAdmin):
    """
    Django admin model for Degreed2LearnerDataTransmissionAudit.
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
    )

    list_per_page = 1000

    class Meta:
        model = Degreed2LearnerDataTransmissionAudit
