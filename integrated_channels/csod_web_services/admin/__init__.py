# -*- coding: utf-8 -*-
"""
Django admin integration for configuring csod_web_services app to communicate with Cornerstone systems.
"""
from __future__ import absolute_import, unicode_literals

from django.contrib import admin
from config_models.admin import ConfigurationModelAdmin

from integrated_channels.csod_web_services.models import (
    CSODWebServicesEnterpriseCustomerConfiguration, CSODWebServicesGlobalConfiguration
)


@admin.register(CSODWebServicesGlobalConfiguration)
class CSODWebServicesGlobalConfigurationAdmin(ConfigurationModelAdmin):
    """
    Django admin model for CSODWebServicesGlobalConfiguration.
    """

    list_display = (
        "complete_learning_object_api_path",
        "create_learning_object_path",
        "update_learning_object_path",
        "session_token_api_path",
    )

    class Meta(object):
        model = CSODWebServicesGlobalConfiguration


@admin.register(CSODWebServicesEnterpriseCustomerConfiguration)
class CSODWebServicesEnterpriseCustomerConfigurationAdmin(admin.ModelAdmin):
    """
    Django admin model for CSODWebServicesEnterpriseCustomerConfiguration.
    """

    list_display = (
        "enterprise_customer_name",
        "active",
        "csod_lo_ws_base_url",
        "csod_lms_ws_base_url",
        "csod_username",
        "csod_user_password",
        "provider",
        "key",
        "secret",
    )

    readonly_fields = (
        "enterprise_customer_name",
    )

    list_filter = ("active",)
    search_fields = ("enterprise_customer_name",)

    class Meta(object):
        model = CSODWebServicesEnterpriseCustomerConfiguration

    def enterprise_customer_name(self, obj):
        """
        Returns: the name for the attached EnterpriseCustomer.

        Args:
            obj: The instance of CSODWebServicesEnterpriseCustomerConfiguration
                being rendered with this admin form.
        """
        return obj.enterprise_customer.name
