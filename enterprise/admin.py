# -*- coding: utf-8 -*-
"""
Django admin integration for enterprise app.
"""
from __future__ import absolute_import, unicode_literals

from simple_history.admin import SimpleHistoryAdmin  # likely a bug in import order checker
from django.contrib import admin

from enterprise.actions import export_as_csv_action
from enterprise.models import EnterpriseCustomer, EnterpriseCustomerBrandingConfiguration, EnterpriseCustomerUser


def get_all_field_names(model):
    """
    Return all fields' names from a model.

    According to `Django documentation`_, ``get_all_field_names`` should become some monstrosity with chained
    iterable ternary nested in a list comprehension. For now, a simpler version of iterating over fields and
    getting their names work, but we might have to switch to full version in future.

    .. _Django documentation: https://docs.djangoproject.com/en/1.8/ref/models/meta/
    """
    return [f.name for f in model._meta.get_fields()]


class EnterpriseCustomerBrandingConfigurationInline(admin.StackedInline):
    """
    Django admin model for EnterpriseCustomerBrandingConfiguration.

    The admin interface has the ability to edit models on the same page as a parent model. These are called inlines.
    https://docs.djangoproject.com/en/1.8/ref/contrib/admin/#django.contrib.admin.StackedInline
    """

    model = EnterpriseCustomerBrandingConfiguration
    can_delete = False


@admin.register(EnterpriseCustomer)
class EnterpriseCustomerAdmin(SimpleHistoryAdmin):
    """
    Django admin model for EnterpriseCustomer.
    """

    list_display = ("name", "uuid", "site", "active", "logo")

    list_filter = ("active",)
    search_fields = ("name", "uuid",)
    inlines = [EnterpriseCustomerBrandingConfigurationInline, ]

    EXPORT_AS_CSV_FIELDS = ["name", "active", "site", "uuid"]

    actions = [
        export_as_csv_action("CSV Export", fields=EXPORT_AS_CSV_FIELDS)
    ]

    class Meta(object):
        model = EnterpriseCustomer

    @staticmethod
    def logo(instance):
        """
        Instance is EnterpriseCustomer.
        """
        if instance.branding_configuration:
            return instance.branding_configuration.logo
        return None


@admin.register(EnterpriseCustomerUser)
class EnterpriseCustomerUserAdmin(admin.ModelAdmin):
    """
    Django admin model for EnterpriseCustomerUser.
    """

    class Meta(object):
        model = EnterpriseCustomerUser

    def get_readonly_fields(self, request, obj=None):
        """
        Make all fields readonly when editing existing model.
        """
        if obj:  # editing an existing object
            return get_all_field_names(self.model)
        return tuple()
