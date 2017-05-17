# -*- coding: utf-8 -*-
"""
Django admin integration for enterprise app.
"""
from __future__ import absolute_import, unicode_literals

from django.conf.urls import url
from django.contrib import admin
from django.utils.html import format_html
from django.contrib.auth import settings
from django.http import HttpResponseRedirect
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _
from django_object_actions import DjangoObjectActions
from simple_history.admin import SimpleHistoryAdmin  # likely a bug in import order checker

from enterprise.admin.actions import export_as_csv_action, get_clear_catalog_id_action
from enterprise.admin.forms import EnterpriseCustomerAdminForm, EnterpriseCustomerIdentityProviderAdminForm
from enterprise.admin.utils import UrlNames
from enterprise.admin.views import EnterpriseCustomerManageLearnersView, TemplatePreviewView
from django.core.urlresolvers import reverse
from enterprise.lms_api import CourseApiClient, EnrollmentApiClient
from enterprise.models import (  # pylint:disable=no-name-in-module
    EnrollmentNotificationEmailTemplate, EnterpriseCustomer, EnterpriseCustomerUser,
    EnterpriseCustomerBrandingConfiguration, EnterpriseCustomerIdentityProvider,
    HistoricalUserDataSharingConsentAudit, PendingEnrollment, PendingEnterpriseCustomerUser,
    EnterpriseCustomerEntitlement, EnterpriseCourseEnrollment
)
from enterprise.utils import get_all_field_names, get_catalog_admin_url, get_catalog_admin_url_template


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

    def ecommerce_coupon_url(self, instance):
        """
        Instance is EnterpriseCustomer. Return e-commerce coupon urls.
        """
        if not instance.entitlement_id:
            return "N/A"

        return format_html(
            '<a href="{base_url}/coupons/{id}" target="_blank">View coupon "{id}" details</a>',
            base_url=settings.ECOMMERCE_PUBLIC_URL_ROOT, id=instance.entitlement_id
        )

    readonly_fields = ('ecommerce_coupon_url',)
    ecommerce_coupon_url.allow_tags = True
    ecommerce_coupon_url.short_description = 'Coupon URL'


@admin.register(EnterpriseCustomer)
class EnterpriseCustomerAdmin(DjangoObjectActions, SimpleHistoryAdmin):
    """
    Django admin model for EnterpriseCustomer.
    """
    list_display = (
        "name",
        "uuid",
        "site",
        "active",
        "logo",
        "identity_provider",
        "enterprise_catalog",
        "ecommerce_coupon_url"
    )

    list_filter = ("active",)
    ordering = ("name",)
    search_fields = ("name", "uuid",)
    inlines = [
        EnterpriseCustomerBrandingConfigurationInline,
        EnterpriseCustomerIdentityProviderInline,
        EnterpriseCustomerEntitlementInline
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

    def ecommerce_coupon_url(self, instance):
        """
        Instance is EnterpriseCustomer. Return e-commerce coupon urls.
        """
        coupon_urls = ''
        entitlements = instance.enterprise_customer_entitlements.all()

        # Return None if EnterpriseCustomer does not have an associated entitlements.
        if not entitlements:
            return None

        for entitlement in entitlements:
            coupon_urls += format_html(
                '<div><a href="{base_url}/coupons/{id}" target="_blank">View coupon "{id}"</a></div>',
                base_url=settings.ECOMMERCE_PUBLIC_URL_ROOT, id=entitlement.entitlement_id
            )

        return coupon_urls

    ecommerce_coupon_url.allow_tags = True
    ecommerce_coupon_url.short_description = 'Ecommerce coupons'

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

    def enterprise_catalog(self, instance):
        """
        Enterprise catalog id with a link to catalog details page.

        Arguments:
            instance (enterprise.models.EnterpriseCustomer): `EnterpriseCustomer` model instance

        Returns:
            catalog id with catalog details link to display in enterprise customer list view.
        """
        # Return None if EnterpriseCustomer does not have an associated catalog.
        if not instance.catalog:
            return None

        catalog_url = get_catalog_admin_url(instance.catalog)
        return "{catalog_id}: <a href='{catalog_url}' target='_blank'>View catalog details.</a>".format(
            catalog_id=instance.catalog,
            catalog_url=catalog_url,
        )

    # Allow html tags in enterprise_catalog column,
    # we need to set it true so that anchor tag is not escaped.
    enterprise_catalog.allow_tags = True

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


class HistoricalUserDataSharingConsentAuditInlineAdmin(admin.TabularInline):
    """
    Inline admin view for UserDataSharingConsentAudit
    """

    model = HistoricalUserDataSharingConsentAudit

    fields = (
        'state',
        'history_date',
    )

    readonly_fields = (
        'state',
        'history_date',
    )

    def has_add_permission(self, request):
        """
        Disable add permission for HistoricalUserDataSharingConsentAudit.
        """
        return False

    def has_delete_permission(self, request, obj=None):
        """
        Disable deletability for HistoricalUserDataSharingConsentAudit.
        """
        return False


@admin.register(EnterpriseCustomerUser)
class EnterpriseCustomerUserAdmin(admin.ModelAdmin):
    """
    Django admin model for EnterpriseCustomerUser.
    """

    class Meta(object):
        model = EnterpriseCustomerUser

    fields = (
        'user_id',
        'enterprise_customer',
        'user_email',
        'username',
        'created',
        'enrolled_courses',
    )

    # Only include fields that are not database-backed; DB-backed fields
    # are dynamically set as read only.
    readonly_fields = (
        'user_email',
        'username',
        'created',
        'enrolled_courses',
    )

    inlines = (
        HistoricalUserDataSharingConsentAuditInlineAdmin,
    )

    def username(self, enterprise_customer_user):
        """
        Return the username for the attached user.

        Args:
            enterprise_customer_user: The instance of EnterpriseCustomerUser
                being rendered with this admin form.
        """
        return enterprise_customer_user.user.username

    def enrolled_courses(self, enterprise_customer_user):
        """
        Return a string representing the courses a given EnterpriseCustomerUser is enrolled in

        Args:
            enterprise_customer_user: The instance of EnterpriseCustomerUser
                being rendered with this admin form.
        """
        courses_string = mark_safe(self.get_enrolled_course_string(enterprise_customer_user))
        return courses_string or 'None'

    def get_readonly_fields(self, request, obj=None):
        """
        Make all fields readonly when editing existing model.
        """
        readonly_fields = super(EnterpriseCustomerUserAdmin, self).get_readonly_fields(request, obj=obj)
        if obj:  # editing an existing object
            return readonly_fields + tuple(get_all_field_names(self.model))
        return readonly_fields

    def get_enrolled_course_string(self, enterprise_customer_user):
        """
        Get an HTML string representing the courses the user is enrolled in.
        """
        enrollment_client = EnrollmentApiClient()
        enrolled_courses = enrollment_client.get_enrolled_courses(self.username(enterprise_customer_user))
        course_details = []
        courses_client = CourseApiClient()
        for course in enrolled_courses:
            course_id = course['course_details']['course_id']
            name = courses_client.get_course_details(course_id)['name']
            course_details.append({'course_id': course_id, 'course_name': name})

        template = '<a href="{url}">{course_name}</a>'
        joiner = '<br/>'
        return joiner.join(
            template.format(
                url=reverse('about_course', args=[course['course_id']]),
                course_name=course['course_name'],
            )
            for course in course_details
        )


@admin.register(PendingEnterpriseCustomerUser)
class PendingEnterpriseCustomerUserAdmin(admin.ModelAdmin):
    """
    Django admin model for PendingEnterpriseCustomerUser
    """

    class Meta(object):
        model = PendingEnterpriseCustomerUser

    fields = (
        'user_email',
        'enterprise_customer',
        'created'
    )

    readonly_fields = (
        'user_email',
        'enterprise_customer',
        'created'
    )


@admin.register(EnrollmentNotificationEmailTemplate)
class EnrollmentNotificationEmailTemplateAdmin(DjangoObjectActions, admin.ModelAdmin):
    """
    Django admin for EnrollmentNotificationEmailTemplate model
    """
    change_actions = ("preview_as_course", "preview_as_program")

    class Meta(object):
        model = EnrollmentNotificationEmailTemplate

    def get_urls(self):
        """
        Returns the additional urls used by the custom object tools.
        """
        preview_urls = [
            url(
                r"^([^/]+)/preview/([a-z]+)/$",
                self.admin_site.admin_view(TemplatePreviewView.as_view()),
                name=UrlNames.PREVIEW_EMAIL_TEMPLATE
            )
        ]
        return preview_urls + super(EnrollmentNotificationEmailTemplateAdmin, self).get_urls()

    def preview(self, obj, preview_type):
        """
        Object tool handler method - redirects to "Preview" view
        """
        # url names coming from get_urls are prefixed with 'admin' namespace
        preview_url = reverse("admin:" + UrlNames.PREVIEW_EMAIL_TEMPLATE, args=(obj.pk, preview_type))
        return HttpResponseRedirect(preview_url)

    def preview_as_course(self, request, obj):  # pylint: disable=unused-argument
        """
        Redirect to preview the HTML template in the context of a course.
        """
        return self.preview(obj, 'course')

    preview_as_course.label = _("Preview (course)")
    preview_as_course.short_description = _(
        "Preview the HTML template rendered in the context of a course enrollment."
    )

    def preview_as_program(self, request, obj):  # pylint: disable=unused-argument
        """
        Redirect to preview the HTML template in the context of a program.
        """
        return self.preview(obj, 'program')

    preview_as_program.label = _("Preview (program)")
    preview_as_program.short_description = _(
        "Preview the HTML template rendered in the context of a program enrollment."
    )


@admin.register(EnterpriseCourseEnrollment)
class EnterpriseCourseEnrollmentAdmin(admin.ModelAdmin):
    """
    Django admin model for EnterpriseCourseEnrollment
    """

    class Meta(object):
        model = EnterpriseCourseEnrollment

    readonly_fields = (
        'enterprise_customer_user',
        'course_id',
        'consent_granted',
    )

    list_display = (
        'enterprise_customer_user',
        'course_id',
        'consent_granted',
    )

    search_fields = ('enterprise_customer_user__user_id', 'course_id',)

    def has_add_permission(self, request):
        """
        Disable add permission for EnterpriseCourseEnrollment.
        """
        return False

    def has_delete_permission(self, request, obj=None):
        """
        Disable deletion for EnterpriseCourseEnrollment.
        """
        return False


@admin.register(PendingEnrollment)
class PendingEnrollmentAdmin(admin.ModelAdmin):
    """
    Django admin model for PendingEnrollment
    """

    class Meta(object):
        model = PendingEnrollment

    readonly_fields = (
        'user',
        'course_id',
        'course_mode',
    )

    list_display = (
        'user',
        'course_id',
        'course_mode',
    )

    search_fields = ('user__user_email', 'course_id',)

    def has_add_permission(self, request):
        """
        Disable add permission for PendingEnrollment.
        """
        return False

    def has_delete_permission(self, request, obj=None):
        """
        Disable deletion for PendingEnrollment.
        """
        return False
