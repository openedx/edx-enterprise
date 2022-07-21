"""
Django admin integration for configuring cornerstone ondemand app to communicate with CSOD systems.
"""

from config_models.admin import ConfigurationModelAdmin

from django.apps import apps
from django.contrib import admin
from django.core.exceptions import ObjectDoesNotExist

from integrated_channels.cornerstone.models import (
    CornerstoneEnterpriseCustomerConfiguration,
    CornerstoneGlobalConfiguration,
    CornerstoneLearnerDataTransmissionAudit,
)


def enterprise_course_enrollment_model():
    """
    Returns the ``EnterpriseCourseEnrollment`` class.
    """
    return apps.get_model('enterprise', 'EnterpriseCourseEnrollment')


def enterprise_customer_user_model():
    """
    Returns the ``EnterpriseCustomerUser`` class.
    """
    return apps.get_model('enterprise', 'EnterpriseCustomerUser')


def enterprise_customer_model():
    """
    Returns the ``EnterpriseCustomer`` class.
    """
    return apps.get_model('enterprise', 'EnterpriseCustomer')


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
        "session_token",
        "session_token_modified",
    )

    raw_id_fields = (
        "enterprise_customer",
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

    raw_id_fields = (
        "user",
    )

    readonly_fields = (
        "enterprise_customer_name",
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

    def enterprise_customer_name(self, obj):
        """
        Returns: the name for the attached EnterpriseCustomer.
        Args:
            obj: The instance of CornerstoneLearnerDataTransmissionAudit
                being rendered with this admin form.
        """

        # a direct foreign key relationship is missing
        # multiple queries here so, avoid adding it to list_display fields
        EnterpriseCourseEnrollment = enterprise_course_enrollment_model()
        EnterpriseCustomerUser = enterprise_customer_user_model()
        EnterpriseCustomer = enterprise_customer_model()
        try:
            ece = EnterpriseCourseEnrollment.objects.get(pk=obj.enterprise_course_enrollment_id)
            ecu = EnterpriseCustomerUser.objects.get(pk=ece.enterprise_customer_user_id)
            ec = EnterpriseCustomer.objects.get(pk=ecu.enterprise_customer_id)
            return ec.name
        except ObjectDoesNotExist:
            return None
