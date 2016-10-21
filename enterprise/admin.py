# -*- coding: utf-8 -*-
"""
Django admin integration for enterprise app.
"""
from __future__ import absolute_import, unicode_literals

from simple_history.admin import SimpleHistoryAdmin  # likely a bug in import order checker
from django.contrib import admin

from enterprise.actions import export_as_csv_action
from enterprise.models import EnterpriseCustomer, EnterpriseCustomerUser


def get_all_field_names(model):
    """
    Return all fields' names from a model.

    According to `Django documentation`_, ``get_all_field_names`` should become some monstrosity with chained
    iterable ternary nested in a list comprehension. For now, a simpler version of iterating over fields and
    getting their names work, but we might have to switch to full version in future.

    .. _Django documentation: https://docs.djangoproject.com/en/1.8/ref/models/meta/
    """
    return [f.name for f in model._meta.get_fields()]


@admin.register(EnterpriseCustomer)
class EnterpriseCustomerAdmin(SimpleHistoryAdmin):
    """
    Django admin model for EnterpriseCustomer.
    """

    list_display = ("name", "uuid", "active",)
    list_filter = ("active",)
    search_fields = ("name", "uuid",)

    EXPORT_AS_CSV_FIELDS = ["name", "active", "uuid"]

    actions = [
        export_as_csv_action("CSV Export", fields=EXPORT_AS_CSV_FIELDS)
    ]

    class Meta(object):
        model = EnterpriseCustomer


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
