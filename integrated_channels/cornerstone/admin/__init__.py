"""
Django admin integration for configuring cornerstone ondemand app to communicate with CSOD systems.
"""

from config_models.admin import ConfigurationModelAdmin

from django.apps import apps
from django.contrib import admin

from integrated_channels.cornerstone.models import (
    CornerstoneEnterpriseCustomerConfiguration,
    CornerstoneGlobalConfiguration,
    CornerstoneLearnerDataTransmissionAudit,
)


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
class CornerstoneEnterpriseCustomerConfigurationAdmin(admin.ModelAdmin):
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
    )

    list_filter = ("active",)

    search_fields = ("enterprise_customer_name",)

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


@admin.register(CornerstoneLearnerDataTransmissionAudit)
class CornerstoneLearnerDataTransmissionAuditAdmin(admin.ModelAdmin):
    """
    Django admin model for CornerstoneLearnerDataTransmissionAudit.
    """
    list_display = (
        "user_email",
        "user_id",
        "enterprise_course_enrollment_id",
        "course_id",
        "status",
    )

    class Meta:
        model = CornerstoneLearnerDataTransmissionAudit

    def user_email(self, obj):
        """
        Returns: the name for the attached EnterpriseCustomer.

        Args:
            obj: The instance of CornerstoneEnterpriseCustomerConfiguration
                being rendered with this admin form.
        """
        return obj.user.email
