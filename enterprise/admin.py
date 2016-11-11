# -*- coding: utf-8 -*-
"""
Django admin integration for enterprise app.
"""
from __future__ import absolute_import, unicode_literals

from simple_history.admin import SimpleHistoryAdmin  # likely a bug in import order checker
from django import forms
from django.contrib import admin

from enterprise import utils
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


class EnterpriseCustomerForm(forms.ModelForm):
    """
    A custom model form to convert a CharField to a TypedChoiceField.

    A model form that converts a CharField to a TypedChoiceField if the choices
    to display are accessible.
    """

    def __init__(self, *args, **kwargs):
        """
        Convert SlugField to TypedChoiceField if choices can be accessed.
        """
        super(EnterpriseCustomerForm, self).__init__(*args, **kwargs)
        idp_choices = utils.get_idp_choices()
        if idp_choices is not None:
            self.fields['identity_provider'] = forms.TypedChoiceField(choices=idp_choices, required=False)

    class Meta:
        model = EnterpriseCustomer
        fields = "__all__"


@admin.register(EnterpriseCustomer)
class EnterpriseCustomerAdmin(SimpleHistoryAdmin):
    """
    Django admin model for EnterpriseCustomer.
    """

    form = EnterpriseCustomerForm
    list_display = ("name", "uuid", "site", "active", "logo", "identity_provider")

    list_filter = ("active",)
    search_fields = ("name", "uuid",)
    inlines = [EnterpriseCustomerBrandingConfigurationInline, ]

    EXPORT_AS_CSV_FIELDS = ["name", "active", "site", "uuid", "identity_provider"]

    actions = [
        export_as_csv_action("CSV Export", fields=EXPORT_AS_CSV_FIELDS)
    ]

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
