# -*- coding: utf-8 -*-
"""
Django admin integration for configuring degreed app to communicate with Degreed systems.
"""

from django.apps import apps
from django.contrib import admin
from django.core.exceptions import ObjectDoesNotExist

from integrated_channels.degreed2.models import (
    Degreed2EnterpriseCustomerConfiguration,
    Degreed2LearnerDataTransmissionAudit,
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


@admin.register(Degreed2EnterpriseCustomerConfiguration)
class Degreed2EnterpriseCustomerConfigurationAdmin(admin.ModelAdmin):
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


@admin.register(Degreed2LearnerDataTransmissionAudit)
class Degreed2LearnerDataTransmissionAuditAdmin(admin.ModelAdmin):
    """
    Django admin model for Degreed2LearnerDataTransmissionAudit.
    """
    list_display = (
        "degreed_user_email",
        "enterprise_course_enrollment_id",
        "course_id",
        "status",
        "modified",
    )

    readonly_fields = (
        "enterprise_customer_name",
    )

    list_per_page = 1000

    class Meta:
        model = Degreed2LearnerDataTransmissionAudit

    def enterprise_customer_name(self, obj):
        """
        Returns: the name for the attached EnterpriseCustomer.
        Args:
            obj: The instance of Degreed2LearnerDataTransmissionAudit
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
