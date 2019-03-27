# -*- coding: utf-8 -*-
"""
Django admin integration for enterprise app.
"""
from __future__ import absolute_import, unicode_literals

import json

from django_object_actions import DjangoObjectActions
from edx_rbac.admin import UserRoleAssignmentAdmin
from simple_history.admin import SimpleHistoryAdmin
from six.moves.urllib.parse import urlencode  # pylint: disable=import-error

from django.conf.urls import url
from django.contrib import admin
from django.contrib.auth import settings
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _

from enterprise.admin.actions import export_as_csv_action, get_clear_catalog_id_action
from enterprise.admin.forms import (
    EnterpriseCustomerAdminForm,
    EnterpriseCustomerIdentityProviderAdminForm,
    EnterpriseCustomerReportingConfigAdminForm,
    EnterpriseFeatureUserRoleAssignmentForm,
    SystemWideEnterpriseUserRoleAssignmentForm,
)
from enterprise.admin.utils import UrlNames
from enterprise.admin.views import (
    EnterpriseCustomerManageLearnersView,
    EnterpriseCustomerTransmitCoursesView,
    TemplatePreviewView,
)
from enterprise.api_client.lms import CourseApiClient, EnrollmentApiClient
from enterprise.models import (
    EnrollmentNotificationEmailTemplate,
    EnterpriseCourseEnrollment,
    EnterpriseCustomer,
    EnterpriseCustomerBrandingConfiguration,
    EnterpriseCustomerCatalog,
    EnterpriseCustomerEntitlement,
    EnterpriseCustomerIdentityProvider,
    EnterpriseCustomerReportingConfiguration,
    EnterpriseCustomerType,
    EnterpriseCustomerUser,
    EnterpriseFeatureUserRoleAssignment,
    PendingEnrollment,
    PendingEnterpriseCustomerUser,
    SystemWideEnterpriseUserRoleAssignment,
)
from enterprise.utils import NotConnectedToOpenEdX, get_all_field_names, get_default_catalog_content_filter

try:
    from openedx.core.djangoapps.catalog.models import CatalogIntegration
except ImportError:
    CatalogIntegration = None


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
    ecommerce_coupon_url.short_description = 'Seat Entitlement URL'


class EnterpriseCustomerCatalogInline(admin.TabularInline):
    """
    Django admin model for EnterpriseCustomerCatalog.
    The admin interface has the ability to edit models on the same page as a parent model. These are called inlines.
    https://docs.djangoproject.com/en/1.8/ref/contrib/admin/#django.contrib.admin.StackedInline
    """

    model = EnterpriseCustomerCatalog
    extra = 0
    can_delete = False

    def get_formset(self, request, obj=None, **kwargs):
        formset = super(EnterpriseCustomerCatalogInline, self).get_formset(request, obj, **kwargs)
        formset.form.base_fields['content_filter'].initial = json.dumps(get_default_catalog_content_filter())
        return formset


@admin.register(EnterpriseCustomerType)
class EnterpriseCustomerTypeAdmin(admin.ModelAdmin):
    """
    Django admin model for EnterpriseCustomerType.
    """

    class Meta(object):
        model = EnterpriseCustomerType

    fields = (
        'name',
    )

    list_display = ('name', )
    search_fields = ('name', )


@admin.register(EnterpriseCustomer)
class EnterpriseCustomerAdmin(DjangoObjectActions, SimpleHistoryAdmin):
    """
    Django admin model for EnterpriseCustomer.
    """
    list_display = (
        'name',
        'slug',
        'customer_type',
        'site',
        'country',
        'active',
        'has_logo',
        'enable_dsc',
        'has_identity_provider',
        'has_enterprise_catalog',
        'has_ecommerce_coupons',
        'uuid',
    )

    list_filter = ('active',)
    ordering = ('name',)
    search_fields = ('name', 'uuid',)
    inlines = [
        EnterpriseCustomerBrandingConfigurationInline,
        EnterpriseCustomerIdentityProviderInline,
        EnterpriseCustomerEntitlementInline,
        EnterpriseCustomerCatalogInline,
    ]

    EXPORT_AS_CSV_FIELDS = ['name', 'active', 'site', 'uuid', 'identity_provider', 'catalog']

    actions = [
        export_as_csv_action('CSV Export', fields=EXPORT_AS_CSV_FIELDS),
        get_clear_catalog_id_action()
    ]

    change_actions = ('manage_learners', 'transmit_courses_metadata')

    form = EnterpriseCustomerAdminForm

    class Meta(object):
        model = EnterpriseCustomer

    def has_ecommerce_coupons(self, instance):
        """
        Return True if provded enterprise customer has ecommerce coupons.

        Arguments:
            instance (enterprise.models.EnterpriseCustomer): `EnterpriseCustomer` model instance
        """
        return instance.enterprise_customer_entitlements.exists()

    has_ecommerce_coupons.boolean = True
    has_ecommerce_coupons.short_description = 'Ecommerce coupons'

    def get_form(self, request, obj=None, **kwargs):
        """
        Retrieve the appropriate form to use, saving the request user
        into the form for use in loading catalog details
        """
        form = super(EnterpriseCustomerAdmin, self).get_form(request, obj, **kwargs)
        form.user = request.user
        return form

    def enable_dsc(self, instance):
        """
        Return True if data sharing consent is enabled for EnterpriseCustomer.

        Arguments:
            instance (enterprise.models.EnterpriseCustomer): `EnterpriseCustomer` model instance
        """
        return instance.enable_data_sharing_consent

    enable_dsc.boolean = True
    enable_dsc.short_description = u'Enable DSC'

    def has_logo(self, instance):
        """
        Return True if EnterpriseCustomer has a logo.

        Arguments:
            instance (enterprise.models.EnterpriseCustomer): `EnterpriseCustomer` model instance
        """
        has_logo = False
        if hasattr(instance, 'branding_configuration') and instance.branding_configuration.logo:
            has_logo = True

        return has_logo

    has_logo.boolean = True
    has_logo.short_description = u'Logo'

    def has_identity_provider(self, instance):
        """
        Return True if EnterpriseCustomer has related identity provider.

        Arguments:
            instance (enterprise.models.EnterpriseCustomer): `EnterpriseCustomer` model instance
        """
        return hasattr(instance, 'enterprise_customer_identity_provider')

    has_identity_provider.boolean = True
    has_identity_provider.short_description = u'Identity provider'

    def has_enterprise_catalog(self, instance):
        """
        Return True if EnterpriseCustomer has catalog id with a link to catalog details page.

        Arguments:
            instance (enterprise.models.EnterpriseCustomer): `EnterpriseCustomer` model instance
        """
        return instance.catalog is not None

    has_enterprise_catalog.boolean = True
    has_enterprise_catalog.short_description = u'Enterprise catalog'

    def manage_learners(self, request, obj):  # pylint: disable=unused-argument
        """
        Object tool handler method - redirects to "Manage Learners" view
        """
        # url names coming from get_urls are prefixed with 'admin' namespace
        manage_learners_url = reverse("admin:" + UrlNames.MANAGE_LEARNERS, args=(obj.uuid,))
        return HttpResponseRedirect(manage_learners_url)

    manage_learners.label = "Manage Learners"
    manage_learners.short_description = "Allows managing learners for this Enterprise Customer"

    def transmit_courses_metadata(self, request, obj):  # pylint: disable=unused-argument
        """
        Object tool handler method - redirects to `Transmit Courses Metadata` view.
        """
        # url names coming from get_urls are prefixed with 'admin' namespace
        transmit_courses_metadata_url = reverse('admin:' + UrlNames.TRANSMIT_COURSES_METADATA, args=(obj.uuid,))
        return HttpResponseRedirect(transmit_courses_metadata_url)

    transmit_courses_metadata.label = 'Transmit Courses Metadata'
    transmit_courses_metadata.short_description = 'Transmit courses metadata for this Enterprise Customer'

    def get_urls(self):
        """
        Returns the additional urls used by the custom object tools.
        """
        customer_urls = [
            url(
                r"^([^/]+)/manage_learners$",
                self.admin_site.admin_view(EnterpriseCustomerManageLearnersView.as_view()),
                name=UrlNames.MANAGE_LEARNERS
            ),
            url(
                r"^([^/]+)/transmit_courses_metadata",
                self.admin_site.admin_view(EnterpriseCustomerTransmitCoursesView.as_view()),
                name=UrlNames.TRANSMIT_COURSES_METADATA
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

    list_display = ('username', 'user_email')
    search_fields = ('user_id',)

    def get_search_results(self, request, queryset, search_term):
        search_term = search_term.strip()
        use_distinct = False

        if search_term:
            queryset = EnterpriseCustomerUser.objects.filter(
                user_id__in=User.objects.filter(
                    Q(email__icontains=search_term) | Q(username__icontains=search_term)
                )
            )
        else:
            queryset, use_distinct = super(EnterpriseCustomerUserAdmin, self).get_search_results(
                request,
                queryset,
                search_term
            )

        return queryset, use_distinct

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
        enrolled_courses = enrollment_client.get_enrolled_courses(enterprise_customer_user.username)
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
    )

    list_display = (
        'enterprise_customer_user',
        'course_id',
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


@admin.register(EnterpriseCustomerCatalog)
class EnterpriseCustomerCatalogAdmin(admin.ModelAdmin):
    """
    Django admin model for EnterpriseCustomerCatalog.
    """
    ordering = ('enterprise_customer__name', 'title')

    class Meta(object):
        model = EnterpriseCustomerCatalog

    list_display = (
        'uuid_nowrap',
        'enterprise_customer',
        'title',
        'discovery_query_url',
    )

    search_fields = (
        'uuid',
        'title',
        'enterprise_customer__name',
        'enterprise_customer__uuid',
    )

    fields = (
        'title',
        'enterprise_customer',
        'content_filter',
        'enabled_course_modes',
        'publish_audit_enrollment_urls',
    )

    def discovery_query_url(self, obj):
        """
        Return discovery url for preview.
        """
        if CatalogIntegration is None:
            raise NotConnectedToOpenEdX(
                _('To get a CatalogIntegration object, this package must be '
                  'installed in an Open edX environment.')
            )
        discovery_root_url = CatalogIntegration.current().get_internal_api_url()
        disc_url = '{discovery_root_url}{search_all_endpoint}?{query_string}'.format(
            discovery_root_url=discovery_root_url,
            search_all_endpoint='search/all/',
            query_string=urlencode(obj.content_filter, doseq=True)
        )
        return format_html(
            '<a href="{url}" target="_blank">Preview</a>',
            url=disc_url
        )
    readonly_fields = ('discovery_query_url',)
    discovery_query_url.allow_tags = True
    discovery_query_url.short_description = 'Preview Catalog Courses'

    def uuid_nowrap(self, obj):
        """
        Inject html for disabling wrap for uuid
        """
        return format_html('<span style="white-space: nowrap;">{uuid}</span>'.format(uuid=obj.uuid))
    uuid_nowrap.short_description = 'UUID'

    def get_form(self, request, obj=None, **kwargs):
        form = super(EnterpriseCustomerCatalogAdmin, self).get_form(request, obj, **kwargs)
        form.base_fields['content_filter'].initial = json.dumps(get_default_catalog_content_filter())
        return form


@admin.register(EnterpriseCustomerReportingConfiguration)
class EnterpriseCustomerReportingConfigurationAdmin(admin.ModelAdmin):
    """
    Django admin model for EnterpriseCustomerReportingConfiguration.
    """

    list_display = (
        "enterprise_customer",
        "active",
        "delivery_method",
        "frequency",
        "data_type",
        "report_type",
    )

    list_filter = ("active",)
    search_fields = ("enterprise_customer__name", "email")
    ordering = ('enterprise_customer__name',)

    form = EnterpriseCustomerReportingConfigAdminForm

    class Meta(object):
        model = EnterpriseCustomerReportingConfiguration

    def get_fields(self, request, obj=None):
        """
        Return the fields that should be displayed on the admin form.
        """
        fields = list(super(EnterpriseCustomerReportingConfigurationAdmin, self).get_fields(request, obj))
        if obj:
            # Exclude password fields when we are editing an existing model.
            return [f for f in fields if f not in {'decrypted_password', 'decrypted_sftp_password'}]

        return fields


@admin.register(SystemWideEnterpriseUserRoleAssignment)
class SystemWideEnterpriseUserRoleAssignmentAdmin(UserRoleAssignmentAdmin):
    """
    Django admin model for SystemWideEnterpriseUserRoleAssignment.
    """

    form = SystemWideEnterpriseUserRoleAssignmentForm

    class Meta(object):
        model = SystemWideEnterpriseUserRoleAssignment


@admin.register(EnterpriseFeatureUserRoleAssignment)
class EnterpriseFeatureUserRoleAssignmentAdmin(UserRoleAssignmentAdmin):
    """
    Django admin model for EnterpriseFeatureUserRoleAssignment.
    """

    form = EnterpriseFeatureUserRoleAssignmentForm

    class Meta(object):
        model = EnterpriseFeatureUserRoleAssignment
