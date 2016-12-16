# -*- coding: utf-8 -*-
"""
Django admin integration for enterprise app.
"""
from __future__ import absolute_import, unicode_literals

from django.conf.urls import url
from django.contrib import admin
from django.contrib.auth import settings
from django.http import HttpResponseRedirect
from django.utils.html import format_html
from django_object_actions import DjangoObjectActions
from simple_history.admin import SimpleHistoryAdmin  # likely a bug in import order checker

from enterprise.admin.actions import export_as_csv_action, get_clear_catalog_id_action
from enterprise.admin.forms import EnterpriseCustomerAdminForm, EnterpriseCustomerIdentityProviderAdminForm
from enterprise.admin.utils import UrlNames
from enterprise.admin.views import EnterpriseCustomerManageLearnersView
from enterprise.django_compatibility import reverse
from enterprise.models import (
    EnterpriseCustomer, EnterpriseCustomerUser, EnterpriseCustomerBrandingConfiguration,
    EnterpriseCustomerIdentityProvider, EnterpriseCustomerEntitlement
)
from enterprise.utils import get_all_field_names


class EnterpriseCustomerBrandingConfigurationInline(admin.StackedInline):
    """
    Django admin model for EnterpriseCustomerBrandingConfiguration.

    The admin interface has the ability to edit models on the same page as a parent model. These are called inlines.
    https://docs.djangoproject.com/en/1.8/ref/contrib/admin/#django.contrib.admin.StackedInline
    """

    model = EnterpriseCustomerBrandingConfiguration
    can_delete = False


class EnterpriseCustomerIdentityProviderInline(admin.StackedInline):
    """
    Django admin model for EnterpriseCustomerIdentityProvider.

    The admin interface has the ability to edit models on the same page as a parent model. These are called inlines.
    https://docs.djangoproject.com/en/1.8/ref/contrib/admin/#django.contrib.admin.StackedInline
    """

    model = EnterpriseCustomerIdentityProvider
    form = EnterpriseCustomerIdentityProviderAdminForm


class EnterpriseCustomerEntitlementInline(admin.StackedInline):
    """
    Django admin model for EnterpriseCustomerEntitlement.

    The admin interface has the ability to edit models on the same page as a parent model. These are called inlines.
    https://docs.djangoproject.com/en/1.8/ref/contrib/admin/#django.contrib.admin.StackedInline
    """
    model = EnterpriseCustomerEntitlement
    extra = 0
    can_delete = True

    fields = ('enterprise_customer', 'entitlement_id', 'ecommerce_coupon_url',)
    readonly_fields = ('ecommerce_coupon_url',)

    def ecommerce_coupon_url(self, obj):
        return format_html(
            '<a href="{base_url}/coupons/{id}" target="_blank">View coupon "{id}" details</a>',
            base_url=settings.ECOMMERCE_PUBLIC_URL_ROOT, id=obj.entitlement_id
        )

    ecommerce_coupon_url.allow_tags = True
    ecommerce_coupon_url.short_description = 'Coupon URL'


@admin.register(EnterpriseCustomer)
class EnterpriseCustomerAdmin(DjangoObjectActions, SimpleHistoryAdmin):
    """
    Django admin model for EnterpriseCustomer.
    """

    list_display = ("name", "uuid", "site", "active", "logo", "identity_provider", "catalog")

    list_filter = ("active",)
    search_fields = ("name", "uuid",)
    inlines = [
        EnterpriseCustomerBrandingConfigurationInline,
        EnterpriseCustomerIdentityProviderInline,
        EnterpriseCustomerEntitlementInline,
    ]

    EXPORT_AS_CSV_FIELDS = ["name", "active", "site", "uuid", "identity_provider", "catalog"]

    actions = [
        export_as_csv_action("CSV Export", fields=EXPORT_AS_CSV_FIELDS),
        get_clear_catalog_id_action()
    ]

    change_actions = ("manage_learners",)

    form = EnterpriseCustomerAdminForm

    class Meta(object):
        model = EnterpriseCustomer

    def get_form(self, request, obj=None, **kwargs):
        """
        Retrieve the appropriate form to use, saving the request user
        into the form for use in loading catalog details
        """
        form = super(EnterpriseCustomerAdmin, self).get_form(request, obj, **kwargs)
        form.user = request.user
        return form

    @staticmethod
    def logo(instance):
        """
        Instance is EnterpriseCustomer.
        """
        if instance.branding_configuration:
            return instance.branding_configuration.logo
        return None

    @staticmethod
    def identity_provider(instance):
        """
        Instance is EnterpriseCustomer.

        Return identity provider name to display in enterprise customer list admin view, and if identity provider name
        is not available then return identity provider id.
        """
        ec_idp = instance.enterprise_customer_identity_provider
        return ec_idp and ec_idp.provider_name or ec_idp.provider_id

    def manage_learners(self, request, obj):  # pylint: disable=unused-argument
        """
        Object tool handler method - redirects to "Manage Learners" view
        """
        # url names coming from get_urls are prefixed with 'admin' namespace
        manage_learners_url = reverse("admin:" + UrlNames.MANAGE_LEARNERS, args=(obj.uuid,))
        return HttpResponseRedirect(manage_learners_url)

    manage_learners.label = "Manage Learners"
    manage_learners.short_description = "Allows managing learners for this Enterprise Customer"

    def get_urls(self):
        """
        Returns the additional urls used by the custom object tools.
        """
        customer_urls = [
            url(
                r"^([^/]+)/manage_learners$",
                self.admin_site.admin_view(EnterpriseCustomerManageLearnersView.as_view()),
                name=UrlNames.MANAGE_LEARNERS
            )
        ]
        return customer_urls + super(EnterpriseCustomerAdmin, self).get_urls()


@admin.register(EnterpriseCustomerUser)
class EnterpriseCustomerUserAdmin(admin.ModelAdmin):
    """
    Django admin model for EnterpriseCustomerUser.
    """

    class Meta(object):
        model = EnterpriseCustomerUser

    fields = ('user_id', 'enterprise_customer')

    def get_readonly_fields(self, request, obj=None):
        """
        Make all fields readonly when editing existing model.
        """
        if obj:  # editing an existing object
            return get_all_field_names(self.model)
        return tuple()


@admin.register(EnterpriseCustomerEntitlement)
class EnterpriseCustomerEntitlementAdmin(admin.ModelAdmin):
    """
    Django admin model for EnterpriseCustomerEntitlement.
    """

    class Meta(object):
        model = EnterpriseCustomerEntitlement

    list_display = ('enterprise_customer', 'entitlement_id', 'ecommerce_coupon_url',)
    fields = ('enterprise_customer', 'entitlement_id',)
    search_fields = ('enterprise_customer', 'entitlement_id',)

    def ecommerce_coupon_url(self, obj):
        return format_html(
            '<a href="{base_url}/coupons/{id}" target="_blank">View coupon "{id}" details</a>',
            base_url=settings.ECOMMERCE_PUBLIC_URL_ROOT, id=obj.entitlement_id
        )

    ecommerce_coupon_url.allow_tags = True
    ecommerce_coupon_url.short_description = 'Coupon URL'
