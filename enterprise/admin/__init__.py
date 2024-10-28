"""
Django admin integration for enterprise app.
"""

import logging

import paramiko
from config_models.admin import ConfigurationModelAdmin
from django_object_actions import DjangoObjectActions
from edx_rbac.admin import UserRoleAssignmentAdmin
from simple_history.admin import SimpleHistoryAdmin

from django.conf import settings
from django.contrib import admin, auth, messages
from django.core.paginator import Paginator
from django.db import connection
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.urls import path, re_path, reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _

from enterprise import constants, models
from enterprise.admin.actions import export_as_csv_action, refresh_catalog
from enterprise.admin.forms import (
    AdminNotificationForm,
    EnterpriseCustomerAdminForm,
    EnterpriseCustomerCatalogAdminForm,
    EnterpriseCustomerIdentityProviderAdminForm,
    EnterpriseCustomerReportingConfigAdminForm,
    EnterpriseFeatureUserRoleAssignmentForm,
    SystemWideEnterpriseUserRoleAssignmentForm,
)
from enterprise.admin.utils import UrlNames
from enterprise.admin.views import (
    CatalogQueryPreviewView,
    EnterpriseCustomerManageLearnerDataSharingConsentView,
    EnterpriseCustomerManageLearnersView,
    EnterpriseCustomerSetupAuthOrgIDView,
    EnterpriseCustomerTransmitCoursesView,
    TemplatePreviewView,
)
from enterprise.api_client.lms import CourseApiClient, EnrollmentApiClient
from enterprise.config.models import UpdateRoleAssignmentsWithCustomersConfig
from enterprise.models import DefaultEnterpriseEnrollmentIntention
from enterprise.utils import (
    discovery_query_url,
    get_all_field_names,
    get_default_catalog_content_filter,
    get_sso_orchestrator_configure_edx_oauth_path,
    localized_utcnow,
)

try:
    from enterprise.api_client.enterprise_catalog import EnterpriseCatalogApiClient
except ImportError:
    EnterpriseCatalogApiClient = None

try:
    from openedx.features.enterprise_support.admin.views import EnrollmentAttributeOverrideView
except ImportError:
    EnrollmentAttributeOverrideView = None
User = auth.get_user_model()


logger = logging.getLogger(__name__)


class EnterpriseCustomerBrandingConfigurationInline(admin.StackedInline):
    """
    Django admin model for EnterpriseCustomerBrandingConfiguration.

    The admin interface has the ability to edit models on the same page as a parent model. These are called inlines.
    https://docs.djangoproject.com/en/1.8/ref/contrib/admin/#django.contrib.admin.StackedInline
    """

    model = models.EnterpriseCustomerBrandingConfiguration
    can_delete = False


class EnterpriseCustomerIdentityProviderInline(admin.StackedInline):
    """
    Django admin model for EnterpriseCustomerIdentityProvider.

    The admin interface has the ability to edit models on the same page as a parent model. These are called inlines.
    https://docs.djangoproject.com/en/1.8/ref/contrib/admin/#django.contrib.admin.StackedInline
    """

    model = models.EnterpriseCustomerIdentityProvider
    form = EnterpriseCustomerIdentityProviderAdminForm
    extra = 0


class EnterpriseCustomerCatalogInline(admin.TabularInline):
    """
    Django admin model for EnterpriseCustomerCatalog.
    The admin interface has the ability to edit models on the same page as a parent model. These are called inlines.
    https://docs.djangoproject.com/en/1.8/ref/contrib/admin/#django.contrib.admin.StackedInline
    """

    model = models.EnterpriseCustomerCatalog
    form = EnterpriseCustomerCatalogAdminForm
    extra = 0
    can_delete = False

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        formset.form.base_fields['content_filter'].initial = get_default_catalog_content_filter()
        return formset


class EnterpriseCustomerDefaultEnterpriseEnrollmentIntentionInline(admin.TabularInline):
    """
    Django admin model for EnterpriseCustomerCatalog.
    The admin interface has the ability to edit models on the same page as a parent model. These are called inlines.
    https://docs.djangoproject.com/en/1.8/ref/contrib/admin/#django.contrib.admin.StackedInline
    """

    model = models.DefaultEnterpriseEnrollmentIntention
    fields = ('content_key', 'course_key', 'course_run_key_for_enrollment',)
    readonly_fields = ('course_key', 'course_run_key_for_enrollment',)
    extra = 0
    can_delete = True

    @admin.display(description='Course key')
    def course_key(self, obj):
        """
        Returns the course run key.
        """
        return obj.course_key

    @admin.display(description='Course run key for enrollment')
    def course_run_key_for_enrollment(self, obj):
        """
        Returns the course run key.
        """
        return obj.course_run_key


class PendingEnterpriseCustomerAdminUserInline(admin.TabularInline):
    """
    Django admin inline model for PendingEnterpriseCustomerAdminUser.
    """

    model = models.PendingEnterpriseCustomerAdminUser
    extra = 0
    fieldsets = (
        (None, {
            'fields': ('user_email', 'get_admin_registration_url')
        }),
    )
    readonly_fields = (
        'get_admin_registration_url',
    )

    @admin.display(
        description='Admin Registration Link'
    )
    def get_admin_registration_url(self, obj):
        """
        Formats the ``admin_registration_url`` model property as an HTML link.
        """
        return format_html('<a href="{0}">{0}</a>'.format(obj.admin_registration_url))


@admin.register(models.EnterpriseCustomerType)
class EnterpriseCustomerTypeAdmin(admin.ModelAdmin):
    """
    Django admin model for EnterpriseCustomerType.
    """

    class Meta:
        model = models.EnterpriseCustomerType

    fields = (
        'name',
    )

    list_display = ('name', )
    search_fields = ('name', )


@admin.register(models.EnterpriseCustomer)
class EnterpriseCustomerAdmin(DjangoObjectActions, SimpleHistoryAdmin):
    """
    Django admin model for EnterpriseCustomer.
    """
    list_display = (
        'name',
        'slug',
        'customer_type',
        'country',
        'active',
        'enable_learner_portal',
        'enable_dsc',
        'has_identity_provider',
        'uuid',
    )

    list_filter = ('active',)
    ordering = ('name',)
    search_fields = ('name', 'uuid',)

    fieldsets = (
        ('Enterprise info', {
            'fields': ('name', 'active', 'slug', 'auth_org_id', 'country')
        }),
        ('Subsidy management screens ', {
            'fields': ('enable_portal_learner_credit_management_screen',
                       'enable_portal_subscription_management_screen',
                       'enable_portal_code_management_screen'),
            'description': ("Select the check boxes below to enable specific subsidy management screens "
                            "on the organization's administrator portal. If an option is left unchecked, "
                            "the customer administrator will not see the screen in their portal "
                            "and will not be able to apply the associated configurations via self-service.")
        }),
        ('Subsidy settings', {
            'fields': ('enable_browse_and_request', 'enable_universal_link'),
            'description': ('Select the check boxes below to enable specific subsidy management settings '
                            'for the administrator portal for subscription and codes customers. '
                            'These should not be selected for customers that only have learner credit.')
        }),
        ('Data sharing consent', {
            'fields': ('enable_data_sharing_consent', 'enforce_data_sharing_consent')
        }),
        ('Email and language ', {
            'fields': ('contact_email', 'reply_to', 'sender_alias', 'default_language', 'hide_labor_market_data')
        }),
        ('Reporting', {
            'fields': ('enable_portal_reporting_config_screen',)
        }),
        ('Integration and learning platform settings', {
            'fields': ('enable_portal_lms_configurations_screen', 'enable_portal_saml_configuration_screen',
                       'enable_slug_login', 'replace_sensitive_sso_username', 'hide_course_original_price',
                       'enable_generation_of_api_credentials')
        }),
        ('Recommended default settings for all enterprise customers', {
            'fields': ('site', 'customer_type', 'enable_learner_portal',
                       'enable_integrated_customer_learner_portal_search',
                       'enable_analytics_screen', 'enable_audit_enrollment',
                       'enable_audit_data_reporting', 'enable_learner_portal_offers',
                       'disable_expiry_messaging_for_learner_credit',
                       'enable_executive_education_2U_fulfillment',
                       'enable_learner_portal_sidebar_message',
                       'learner_portal_sidebar_content', 'enable_pathways', 'enable_programs',
                       'enable_demo_data_for_analytics_and_lpr', 'enable_academies', 'enable_one_academy'),
            'description': ('The following default settings should be the same for '
                            'the majority of enterprise customers, '
                            'and are either rarely used, unlikely to be sold, '
                            'or unlikely to be changed from the default.')
        }),
    )

    inlines = [
        EnterpriseCustomerBrandingConfigurationInline,
        EnterpriseCustomerIdentityProviderInline,
        EnterpriseCustomerCatalogInline,
        EnterpriseCustomerDefaultEnterpriseEnrollmentIntentionInline,
        PendingEnterpriseCustomerAdminUserInline,
    ]

    EXPORT_AS_CSV_FIELDS = ['name', 'active', 'site', 'uuid', 'identity_provider']

    actions = [
        export_as_csv_action('CSV Export', fields=EXPORT_AS_CSV_FIELDS),
    ]

    change_actions = (
        'setup_auth_org_id',
        'manage_learners',
        'manage_learners_data_sharing_consent',
        'transmit_courses_metadata',
    )

    def get_change_actions(self, *args, **kwargs):
        """
        Buttons that appear at the top of the "Change Enterprise Customer" page.

        Due to a known deficiency in the upstream django_object_actions library, we must STILL define change_actions
        above with all possible values.
        """
        change_actions = (
            'manage_learners',
            'manage_learners_data_sharing_consent',
            'transmit_courses_metadata',
        )
        # Add the "Setup Auth org id" button only if it is configured.
        if get_sso_orchestrator_configure_edx_oauth_path():
            change_actions = ('setup_auth_org_id',) + change_actions
        return change_actions

    form = EnterpriseCustomerAdminForm

    class Meta:
        model = models.EnterpriseCustomer

    def get_search_results(self, request, queryset, search_term):
        original_queryset = queryset
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)

        # default admin search uses `__icontains` and it will return nothing if uuid
        # contains hyphens even if that uuid has an associated record present in model
        # for more details see https://code.djangoproject.com/ticket/29915
        if not queryset:
            queryset, use_distinct = super().get_search_results(
                request, original_queryset, search_term.replace('-', '')
            )

        return queryset, use_distinct

    def change_view(self, request, object_id, form_url='', extra_context=None):
        catalog_uuid = EnterpriseCustomerCatalogAdminForm.get_catalog_preview_uuid(request.POST)
        if catalog_uuid:
            catalog_content_metadata_url = \
                EnterpriseCatalogApiClient.get_content_metadata_url(catalog_uuid)
            return HttpResponseRedirect(catalog_content_metadata_url)
        return super().change_view(
            request,
            object_id,
            form_url,
            extra_context=extra_context
        )

    def get_form(self, request, obj=None, change=False, **kwargs):
        """
        Retrieve the appropriate form to use, saving the request user
        into the form for use in loading catalog details
        """
        form = super().get_form(request, obj, change, **kwargs)
        form.user = request.user
        return form

    @admin.display(
        description='Enable DSC',
        boolean=True,
    )
    def enable_dsc(self, instance):
        """
        Return True if data sharing consent is enabled for EnterpriseCustomer.

        Arguments:
            instance (enterprise.models.EnterpriseCustomer): `EnterpriseCustomer` model instance
        """
        return instance.enable_data_sharing_consent

    @admin.display(
        description='Logo',
        boolean=True,
    )
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

    @admin.display(
        description='Identity provider',
        boolean=True,
    )
    def has_identity_provider(self, instance):
        """
        Return True if EnterpriseCustomer has related identity provider.

        Arguments:
            instance (enterprise.models.EnterpriseCustomer): `EnterpriseCustomer` model instance
        """
        return instance.has_identity_providers

    @admin.action(
        description="Clear Data Sharing Consent for a Learner."
    )
    def manage_learners_data_sharing_consent(self, request, obj):
        """
        Object tool handler method - redirects to "Clear Learners Data Sharing Consent" view
        """
        # url names coming from get_urls are prefixed with 'admin' namespace
        return HttpResponseRedirect(reverse("admin:" + UrlNames.MANAGE_LEARNERS_DSC, args=(obj.uuid,)))

    manage_learners_data_sharing_consent.label = "Clear Data Sharing Consent"

    @admin.action(
        description="Allows managing learners for this Enterprise Customer"
    )
    def manage_learners(self, request, obj):
        """
        Object tool handler method - redirects to "Manage Learners" view
        """
        # url names coming from get_urls are prefixed with 'admin' namespace
        manage_learners_url = reverse("admin:" + UrlNames.MANAGE_LEARNERS, args=(obj.uuid,))
        return HttpResponseRedirect(manage_learners_url)

    manage_learners.label = "Manage Learners"

    @admin.action(
        description='Transmit courses metadata for this Enterprise Customer'
    )
    def transmit_courses_metadata(self, request, obj):
        """
        Object tool handler method - redirects to `Transmit Courses Metadata` view.
        """
        # url names coming from get_urls are prefixed with 'admin' namespace
        transmit_courses_metadata_url = reverse('admin:' + UrlNames.TRANSMIT_COURSES_METADATA, args=(obj.uuid,))
        return HttpResponseRedirect(transmit_courses_metadata_url)

    transmit_courses_metadata.label = 'Transmit Courses Metadata'

    @admin.action(
        description='Setup auth_org_id for this Enterprise Customer'
    )
    def setup_auth_org_id(self, request, obj):
        """
        Object tool handler method - redirects to `Setup Auth org id` view.
        """
        # url names coming from get_urls are prefixed with 'admin' namespace
        setup_auth_org_id_url = reverse('admin:' + UrlNames.SETUP_AUTH_ORG_ID, args=(obj.uuid,))
        return HttpResponseRedirect(setup_auth_org_id_url)

    setup_auth_org_id.label = 'Setup Auth org id'

    def get_urls(self):
        """
        Returns the additional urls used by the custom object tools.
        """
        customer_urls = [
            re_path(
                r"^([^/]+)/manage_learners$",
                self.admin_site.admin_view(EnterpriseCustomerManageLearnersView.as_view()),
                name=UrlNames.MANAGE_LEARNERS,
            ),
            re_path(
                r"^([^/]+)/clear_learners_data_sharing_consent",
                self.admin_site.admin_view(EnterpriseCustomerManageLearnerDataSharingConsentView.as_view()),
                name=UrlNames.MANAGE_LEARNERS_DSC,
            ),
            re_path(
                r"^([^/]+)/transmit_courses_metadata",
                self.admin_site.admin_view(EnterpriseCustomerTransmitCoursesView.as_view()),
                name=UrlNames.TRANSMIT_COURSES_METADATA,
            ),
            re_path(
                r"^([^/]+)/setup_auth_org_id",
                self.admin_site.admin_view(EnterpriseCustomerSetupAuthOrgIDView.as_view()),
                name=UrlNames.SETUP_AUTH_ORG_ID,
            ),
        ]
        return customer_urls + super().get_urls()


@admin.register(models.EnterpriseCustomerUser)
class EnterpriseCustomerUserAdmin(admin.ModelAdmin):
    """
    Django admin model for EnterpriseCustomerUser.
    """

    class Meta:
        model = models.EnterpriseCustomerUser

    fields = (
        'user_id',
        'enterprise_customer',
        'user_email',
        'username',
        'created',
        'enterprise_enrollments',
        'other_enrollments',
        'invite_key',
        'active',
        'should_inactivate_other_customers',
    )

    # Only include fields that are not database-backed; DB-backed fields
    # are dynamically set as read only.
    readonly_fields = (
        'user_email',
        'username',
        'created',
        'enterprise_enrollments',
        'other_enrollments',
    )

    list_display = ('username', 'user_email', 'get_enterprise_customer')
    search_fields = ('user_id', 'user_email',)

    @admin.display(
        description='Enterprise Customer'
    )
    def get_enterprise_customer(self, obj):
        """
        Returns the name of enterprise customer linked with the enterprise customer user.
        """
        return obj.enterprise_customer.name

    def get_search_results(self, request, queryset, search_term):
        search_term = search_term.strip()
        use_distinct = False

        if search_term:
            queryset = models.EnterpriseCustomerUser.objects.filter(
                user_id__in=User.objects.filter(
                    Q(email__icontains=search_term) | Q(username__icontains=search_term)
                )
            )
        else:
            queryset, use_distinct = super().get_search_results(
                request,
                queryset,
                search_term
            )

        return queryset, use_distinct

    def enterprise_enrollments(self, enterprise_customer_user):
        """
        Return a string representing a given EnterpriseCustomerUser's enterprise course enrollments

        Args:
            enterprise_customer_user: The instance of EnterpriseCustomerUser
                being rendered with this admin form.
        """
        enterprise_course_ids = self._get_enterprise_course_enrollments(enterprise_customer_user)
        courses_string = mark_safe(self.get_enrolled_course_string(enterprise_course_ids))
        return courses_string or 'None'

    def other_enrollments(self, enterprise_customer_user):
        """
        Return a string representing a given EnterpriseCustomerUser's non-enterprise course enrollments

        Args:
            enterprise_customer_user: The instance of EnterpriseCustomerUser
                being rendered with this admin form.
        """
        all_course_ids = self._get_all_enrollments(enterprise_customer_user)
        enterprise_course_ids = self._get_enterprise_course_enrollments(enterprise_customer_user)
        # remove overlapping enterprise enrollments from all enrollments
        course_ids = set(all_course_ids) - set(enterprise_course_ids)
        courses_string = mark_safe(self.get_enrolled_course_string(course_ids))
        return courses_string or 'None'

    def _get_enterprise_course_enrollments(self, enterprise_customer_user):
        """
        Return a list of course ids representing a given EnterpriseCustomerUser's enterprise course enrollments

        Args:
            enterprise_customer_user: The instance of EnterpriseCustomerUser
                being rendered with this admin form.
        """
        enrollments = models.EnterpriseCourseEnrollment.objects.filter(
            enterprise_customer_user=enterprise_customer_user
        )
        return [enrollment.course_id for enrollment in enrollments]

    def _get_all_enrollments(self, enterprise_customer_user):
        """
        Return a list of course ids representing a given EnterpriseCustomerUser's course enrollments,
        including both enterprise and non-enterprise course enrollments

        Args:
            enterprise_customer_user: The instance of EnterpriseCustomerUser
                being rendered with this admin form.
        """
        enrollment_client = EnrollmentApiClient()
        enrollments = enrollment_client.get_enrolled_courses(enterprise_customer_user.username)
        return [enrollment['course_details']['course_id'] for enrollment in enrollments]

    def get_readonly_fields(self, request, obj=None):
        """
        Make all fields readonly when editing existing model.
        """
        readonly_fields = super().get_readonly_fields(request, obj=obj)
        if obj:  # editing an existing object
            return readonly_fields + tuple(get_all_field_names(self.model))
        return readonly_fields

    def get_enrolled_course_string(self, course_ids):
        """
        Get an HTML string representing the courses the user is enrolled in.
        """
        courses_client = CourseApiClient()
        course_details = []
        for course_id in course_ids:
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


@admin.register(models.PendingEnterpriseCustomerUser)
class PendingEnterpriseCustomerUserAdmin(admin.ModelAdmin):
    """
    Django admin model for PendingEnterpriseCustomerUser
    """

    class Meta:
        model = models.PendingEnterpriseCustomerUser

    fields = (
        'user_email',
        'enterprise_customer',
        'created'
    )

    search_fields = (
        'user_email',
        'id'
    )

    readonly_fields = (
        'user_email',
        'enterprise_customer',
        'created'
    )


@admin.register(models.PendingEnterpriseCustomerAdminUser)
class PendingEnterpriseCustomerAdminUserAdmin(admin.ModelAdmin):
    """
    Django admin model for PendingEnterpriseCustomerAdminUser
    """

    class Meta:
        model = models.PendingEnterpriseCustomerAdminUser

    fields = (
        'user_email',
        'enterprise_customer',
        'get_admin_registration_url',
    )

    readonly_fields = (
        'get_admin_registration_url',
    )

    list_display = (
        'user_email',
        'get_enterprise_customer',
        'get_admin_registration_url',
    )

    search_fields = (
        'user_email',
        'enterprise_customer__name',
    )

    @admin.display(
        description='Enterprise Customer'
    )
    def get_enterprise_customer(self, obj):
        """
        Returns the name of the associated EnterpriseCustomer.
        """
        return obj.enterprise_customer.name

    @admin.display(
        description='Admin Registration Link'
    )
    def get_admin_registration_url(self, obj):
        """
        Formats the ``admin_registration_url`` model property as an HTML link.
        """
        return format_html('<a href="{0}">{0}</a>'.format(obj.admin_registration_url))


@admin.register(models.EnrollmentNotificationEmailTemplate)
class EnrollmentNotificationEmailTemplateAdmin(DjangoObjectActions, admin.ModelAdmin):
    """
    Django admin for EnrollmentNotificationEmailTemplate model
    """
    change_actions = ("preview_as_course", "preview_as_program")

    class Meta:
        model = models.EnrollmentNotificationEmailTemplate

    def get_urls(self):
        """
        Returns the additional urls used by the custom object tools.
        """
        preview_urls = [
            re_path(
                r"^([^/]+)/preview/([a-z]+)/$",
                self.admin_site.admin_view(TemplatePreviewView.as_view()),
                name=UrlNames.PREVIEW_EMAIL_TEMPLATE
            )
        ]
        return preview_urls + super().get_urls()

    def preview(self, obj, preview_type):
        """
        Object tool handler method - redirects to "Preview" view
        """
        # url names coming from get_urls are prefixed with 'admin' namespace
        preview_url = reverse("admin:" + UrlNames.PREVIEW_EMAIL_TEMPLATE, args=(obj.pk, preview_type))
        return HttpResponseRedirect(preview_url)

    @admin.action(
        description=_(
            "Preview the HTML template rendered in the context of a course enrollment."
        )
    )
    def preview_as_course(self, request, obj):
        """
        Redirect to preview the HTML template in the context of a course.
        """
        return self.preview(obj, 'course')

    preview_as_course.label = _("Preview (course)")

    @admin.action(
        description=_(
            "Preview the HTML template rendered in the context of a program enrollment."
        )
    )
    def preview_as_program(self, request, obj):
        """
        Redirect to preview the HTML template in the context of a program.
        """
        return self.preview(obj, 'program')

    preview_as_program.label = _("Preview (program)")


@admin.register(models.EnterpriseCourseEnrollment)
class EnterpriseCourseEnrollmentAdmin(admin.ModelAdmin):
    """
    Django admin model for EnterpriseCourseEnrollment
    """

    class Meta:
        model = models.EnterpriseCourseEnrollment

    readonly_fields = (
        'enterprise_customer_user',
        'course_id',
        'saved_for_later',
        'license_uuid',
    )

    list_display = (
        'enterprise_customer_user',
        'course_id',
        'saved_for_later',
        'unenrolled_at',
    )

    change_list_template = "enterprise/admin/enterprise_course_enrollments_list.html"
    search_fields = ('enterprise_customer_user__user_id', 'course_id',)

    def license_uuid(self, obj):
        """
        Return the subscription license UUID (if any exists)  associated with this enrollment.
        """
        return str(obj.license.license_uuid)

    def has_add_permission(self, request):
        """
        Disable add permission for EnterpriseCourseEnrollment.
        """
        return False

    def has_delete_permission(self, request, obj=None):
        """
        Disable deletion for EnterpriseCourseEnrollment.
        """
        features = getattr(settings, 'FEATURES', {})
        return features.get(constants.ALLOW_ADMIN_ENTERPRISE_COURSE_ENROLLMENT_DELETION, False)

    def changelist_view(self, request, extra_context=None):
        """
        Override to conditionally show the button.
        """
        extra_context = extra_context or {}
        extra_context['attr_override_button'] = bool(EnrollmentAttributeOverrideView)
        return super().changelist_view(request, extra_context=extra_context)

    def get_urls(self):
        """
        Append `Enrollment Attribute Override` view url with default urls
        """
        custom_urls = []
        if EnrollmentAttributeOverrideView:
            custom_urls = [
                path('override_attributes/', self.admin_site.admin_view(EnrollmentAttributeOverrideView.as_view()),
                     name='enterprise_override_attributes'
                     ),
            ]

        return custom_urls + super().get_urls()


@admin.register(models.PendingEnrollment)
class PendingEnrollmentAdmin(admin.ModelAdmin):
    """
    Django admin model for PendingEnrollment
    """

    class Meta:
        model = models.PendingEnrollment

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


@admin.register(models.EnterpriseCatalogQuery)
class EnterpriseCatalogQueryAdmin(admin.ModelAdmin):
    """
    Django admin model for EnterpriseCatalogQuery.
    """

    class Meta:
        model = models.EnterpriseCatalogQuery

    fields = (
        'uuid',
        'title',
        'discovery_query_url',
        'content_filter',
    )

    def get_urls(self):
        """
        Returns the additional urls used by the custom object tools.
        """
        preview_urls = [
            re_path(
                r"^([^/]+)/preview/$",
                self.admin_site.admin_view(CatalogQueryPreviewView.as_view()),
                name=UrlNames.PREVIEW_QUERY_RESULT
            )
        ]
        return preview_urls + super().get_urls()

    list_display = (
        'title',
        'discovery_query_url',
    )

    @admin.display(
        description='Preview Catalog Courses'
    )
    def discovery_query_url(self, obj):
        """
        Return discovery url for preview.
        """
        url = reverse("admin:" + UrlNames.PREVIEW_QUERY_RESULT, args=(obj.pk,))
        return format_html(
            '<a href="{url}" target="_blank">Preview</a>',
            url=url
        )

    def has_delete_permission(self, request, obj=None):
        return False

    readonly_fields = ('discovery_query_url', 'uuid')


@admin.register(models.EnterpriseCustomerCatalog)
class EnterpriseCustomerCatalogAdmin(admin.ModelAdmin):
    """
    Django admin model for EnterpriseCustomerCatalog.
    """
    ordering = ('enterprise_customer__name', 'title')
    actions = [refresh_catalog]

    class Meta:
        model = models.EnterpriseCustomerCatalog

    class Media:
        js = ('enterprise/admin/enterprise_customer_catalog.js',)

    list_display = (
        'uuid_nowrap',
        'enterprise_customer',
        'title',
        'preview_catalog_url',
    )

    search_fields = (
        'uuid',
        'title',
        'enterprise_customer__name',
        'enterprise_customer__uuid',
    )

    autocomplete_fields = ['enterprise_customer']

    fields = (
        'title',
        'enterprise_customer',
        'enterprise_catalog_query',
        'content_filter',
        'enabled_course_modes',
        'publish_audit_enrollment_urls',
    )

    @admin.display(
        description='Preview Catalog Courses'
    )
    def preview_catalog_url(self, obj):
        """
        Return enterprise catalog url for preview.
        """
        catalog_content_metadata_url = \
            EnterpriseCatalogApiClient.get_content_metadata_url(obj.uuid)
        return format_html(
            '<a href="{url}" target="_blank">Preview</a>',
            url=catalog_content_metadata_url
        )

    readonly_fields = ('preview_catalog_url',)

    @admin.display(
        description='UUID'
    )
    def uuid_nowrap(self, obj):
        """
        Inject html for disabling wrap for uuid
        """
        return format_html('<span style="white-space: nowrap;">{uuid}</span>'.format(uuid=obj.uuid))

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super().get_form(request, obj, change, **kwargs)
        form.base_fields['content_filter'].initial = get_default_catalog_content_filter()
        return form

    def get_actions(self, request):
        """
        Disallow the delete selected action as that does not send a DELETE request to enterprise-catalog
        """
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions


@admin.register(models.EnterpriseCustomerReportingConfiguration)
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
    autocomplete_fields = ['enterprise_customer']
    ordering = ('enterprise_customer__name',)

    form = EnterpriseCustomerReportingConfigAdminForm

    class Meta:
        model = models.EnterpriseCustomerReportingConfiguration

    def get_fields(self, request, obj=None):
        """
        Return the fields that should be displayed on the admin form.
        """
        fields = list(super().get_fields(request, obj))
        if obj:
            # Exclude password fields when we are editing an existing model.
            return [f for f in fields if f not in {'decrypted_password', 'decrypted_sftp_password'}]

        return fields

    def get_readonly_fields(self, request, obj=None):
        """
        Conditionally add the test_sftp_server to the readonly fields.
        """
        readonly_fields = list(super().get_readonly_fields(request, obj))
        if obj and obj.delivery_method == models.EnterpriseCustomerReportingConfiguration.DELIVERY_METHOD_SFTP:
            readonly_fields.append('test_sftp_server')
        return readonly_fields

    def test_sftp_server(self, obj):
        """
        Add a button to test the SFTP server connection.
        """
        return format_html(
            '<a class="button" href="{}">Test SFTP Server Connection</a>',
            reverse('admin:test_sftp_connection', args=[obj.pk]),
        )

    test_sftp_server.short_description = 'Test SFTP Server'
    test_sftp_server.allow_tags = True

    def get_urls(self):
        """
        Extend the admin URLs to include the custom test server URL.
        """
        urls = super().get_urls()
        custom_urls = [
            path('test-sftp-connection/<int:pk>/', self.admin_site.admin_view(self.test_sftp_connection),
                 name='test_sftp_connection'),
        ]
        return custom_urls + urls

    def test_sftp_connection(self, request, pk):
        """
        Custom admin view to test the SFTP server connection.
        """
        config = self.get_object(request, pk)
        if config:
            try:
                transport = paramiko.Transport((config.sftp_hostname, config.sftp_port))
                transport.connect(username=config.sftp_username, password=config.decrypted_sftp_password)
                sftp = paramiko.SFTPClient.from_transport(transport)
                sftp.close()
                transport.close()
                self.message_user(request, "Successfully connected to the SFTP server.")
            except Exception as e:  # pylint: disable=broad-except
                self.message_user(request, f"Failed to connect to the SFTP server: {e}", level=messages.ERROR)

        return HttpResponseRedirect(reverse('admin:enterprise_enterprisecustomerreportingconfiguration_changelist'))


class BigTableMysqlPaginator(Paginator):
    """
    A paginator that uses INFORMATION_SCHEMA.TABLES to estimate
    the total number of rows in a table.
    """
    ARBITRARILY_LARGE_NUMBER = 10000000

    # pylint: disable=attribute-defined-outside-init
    @property
    def count(self):  # pylint: disable=invalid-overridden-method
        """
        Returns the number of items in the object list (possibly an estimate).
        """
        query = self.object_list.query

        if query.where:
            return super().count
        if not getattr(self, '_whole_table_count', None):
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        'SELECT TABLE_ROWS FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = %s',
                        [query.model._meta.db_table]
                    )
                    self._whole_table_count = int(cursor.fetchone()[0])
            except Exception:  # pylint: disable=broad-except
                logger.exception(
                    'Cannot get count estimate for %s from INFORMATION_SCHEMA.TABLES',
                    query.model,
                )
                self._whole_table_count = self.ARBITRARILY_LARGE_NUMBER
        return self._whole_table_count


@admin.register(models.SystemWideEnterpriseUserRoleAssignment)
class SystemWideEnterpriseUserRoleAssignmentAdmin(UserRoleAssignmentAdmin):
    """
    Django admin model for SystemWideEnterpriseUserRoleAssignment.
    """

    paginator = BigTableMysqlPaginator
    show_full_result_count = False

    fields = ('user', 'role', 'enterprise_customer', 'applies_to_all_contexts')

    list_display = ('user', 'role', 'enterprise_customer', 'applies_to_all_contexts')
    # This tells Django to use select_related() in retrieving the list of objects on the change list page.
    # It should save some queries
    list_select_related = (
        'user',
        'role',
        'enterprise_customer',
    )
    list_per_page = 25

    search_fields = ('user__email', 'role__name', 'enterprise_customer__name')

    form = SystemWideEnterpriseUserRoleAssignmentForm

    class Meta:
        model = models.SystemWideEnterpriseUserRoleAssignment


@admin.register(models.EnterpriseFeatureUserRoleAssignment)
class EnterpriseFeatureUserRoleAssignmentAdmin(UserRoleAssignmentAdmin):
    """
    Django admin model for EnterpriseFeatureUserRoleAssignment.
    """

    form = EnterpriseFeatureUserRoleAssignmentForm

    class Meta:
        model = models.EnterpriseFeatureUserRoleAssignment


admin.site.register(UpdateRoleAssignmentsWithCustomersConfig, ConfigurationModelAdmin)


@admin.register(models.AdminNotificationRead)
class AdminNotificationReadAdmin(admin.ModelAdmin):
    """
    Django admin for AdminNotificationRead model.
    """

    model = models.AdminNotificationRead
    list_display = ('id', 'enterprise_customer_user', 'admin_notification', 'is_read', 'created', 'modified')


@admin.register(models.AdminNotification)
class AdminNotificationAdmin(admin.ModelAdmin):
    """
    Django admin for AdminNotification model.
    """

    model = models.AdminNotification
    form = AdminNotificationForm
    list_display = ('id', 'title', 'text', 'is_active', 'start_date', 'expiration_date', 'created', 'modified')
    filter_horizontal = ('admin_notification_filter',)


@admin.register(models.AdminNotificationFilter)
class AdminNotificationFilterAdmin(admin.ModelAdmin):
    """
    Django admin for models.AdminNotificationFilter model.
    """

    model = models.AdminNotificationFilter
    list_display = ('id', 'filter', 'created', 'modified')


@admin.register(models.EnterpriseCustomerInviteKey)
class EnterpriseCustomerInviteKeyAdmin(admin.ModelAdmin):
    """
    Django admin model for EnterpriseCustomerInviteKey.
    """

    fields = (
        'enterprise_customer',
        'usage_count',
        'usage_limit',
        'expiration_date',
        'is_active',
    )

    readonly_fields = ('uuid', 'usage_count')

    list_display = (
        'uuid',
        'enterprise_customer_id',
        'usage_limit',
        'expiration_date',
        'is_active',
    )

    list_filter = ('is_active',)

    search_fields = (
        'uuid__startswith',
        'enterprise_customer__name__startswith',
    )

    class Meta:
        model = models.EnterpriseCustomerInviteKey

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = super().get_readonly_fields(request, obj=obj)

        if not obj or not obj.is_active:
            return readonly_fields + ('is_active',)

        return readonly_fields


@admin.register(models.ChatGPTResponse)
class ChatGPTResponseAdmin(admin.ModelAdmin):
    """
    Django admin for ChatGPTResponse model.
    """

    model = models.ChatGPTResponse
    list_display = ('uuid', 'prompt_type', 'enterprise_customer', 'prompt_hash', 'created', )
    readonly_fields = ('prompt_type', 'prompt', 'response', 'prompt_hash', 'created', 'modified', )
    list_filter = ('prompt_type', )


@admin.register(models.EnterpriseCustomerSsoConfiguration)
class EnterpriseCustomerSsoConfigurationAdmin(DjangoObjectActions, admin.ModelAdmin):
    """
    Django admin for models.EnterpriseCustomerSsoConfigurationAdmin model.
    """

    model = models.EnterpriseCustomerSsoConfiguration
    list_display = ('uuid', 'enterprise_customer', 'active', 'identity_provider', 'created', 'configured_at')
    change_actions = ['mark_configured']

    @admin.action(
        description="Allows for marking a config as configured. This is useful for testing while the SSO"
        "orchestrator is under constructions.",
    )
    def mark_configured(self, request, obj):
        """
        Object tool handler method - marks the config as configured.
        """
        obj.configured_at = localized_utcnow()
        obj.save()

    mark_configured.label = "Mark as Configured"


@admin.register(models.EnterpriseGroup)
class EnterpriseGroupAdmin(admin.ModelAdmin):
    """
    Django admin for EnterpriseGroup model.
    """
    model = models.EnterpriseGroup
    list_display = ('uuid', 'enterprise_customer', )
    list_filter = ('group_type',)
    search_fields = (
        'uuid',
        'name',
        'enterprise_customer__name',
        'enterprise_customer__uuid',
    )
    readonly_fields = ('count', 'members',)

    autocomplete_fields = ['enterprise_customer']

    def members(self, obj):
        """
        Return the non-deleted members of a group
        """
        return obj.get_all_learners()

    @admin.display(description="Number of members in group")
    def count(self, obj):
        """
        Return the number of members in a group
        """
        return len(obj.get_all_learners())


@admin.register(models.EnterpriseGroupMembership)
class EnterpriseGroupMembershipAdmin(admin.ModelAdmin):
    """
    Django admin for EnterpriseGroupMembership model.
    """
    model = models.EnterpriseGroupMembership
    list_display = ('group', 'membership_user', 'is_removed')
    list_filter = ('is_removed',)
    search_fields = (
        'uuid',
        'group__uuid',
        'group__enterprise_customer__uuid',
        'enterprise_customer_user__id',
        'pending_enterprise_customer_user__user_email',
    )
    autocomplete_fields = (
        'group',
        'enterprise_customer_user',
        'pending_enterprise_customer_user',
    )

    def get_queryset(self, request):
        """
        Return a QuerySet of all model instances.
        """
        show_soft_deletes = request.GET.get('is_removed__exact', False)
        if show_soft_deletes:
            qs = self.model.all_objects.get_queryset()
        else:
            qs = self.model.available_objects.get_queryset()

        ordering = self.get_ordering(request)
        if ordering:
            qs = qs.order_by(*ordering)

        return qs


@admin.register(models.LearnerCreditEnterpriseCourseEnrollment)
class LearnerCreditEnterpriseCourseEnrollmentAdmin(admin.ModelAdmin):
    """
    Django admin model for LearnerCreditEnterpriseCourseEnrollmentAdmin.
    """
    list_display = (
        'uuid',
        'fulfillment_type',
        'enterprise_course_enrollment',
        'modified',
    )

    readonly_fields = (
        'uuid',
        'enterprise_course_enrollment',
    )

    list_filter = ('is_revoked',)

    search_fields = (
        'uuid',
        'enterprise_course_enrollment__id'
        'enterprise_course_enrollment__user_id',
    )

    ordering = ('-modified',)

    class Meta:
        fields = '__all__'
        model = models.LearnerCreditEnterpriseCourseEnrollment


@admin.register(models.DefaultEnterpriseEnrollmentIntention)
class DefaultEnterpriseEnrollmentIntentionAdmin(admin.ModelAdmin):
    """
    Django admin model for DefaultEnterpriseEnrollmentIntentions.
    """
    list_display = (
        'uuid',
        'enterprise_customer',
        'content_key',
        'content_type',
        'is_removed',
    )

    list_filter = ('is_removed',)

    fields = (
        'enterprise_customer',
        'content_key',
        'uuid',
        'is_removed',
        'content_type',
        'course_key',
        'course_run_key',
        'created',
        'modified',
    )

    readonly_fields = (
        'uuid',
        'content_type',
        'course_key',
        'course_run_key',
        'created',
        'modified',
    )

    search_fields = (
        'uuid',
        'enterprise_customer__uuid',
        'content_key',
    )

    ordering = ('-modified',)

    class Meta:
        model = models.DefaultEnterpriseEnrollmentIntention

    def get_queryset(self, request):
        """
        Return a QuerySet of all model instances.
        """
        return self.model.all_objects.get_queryset()

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        """
        Customize the form field for the `is_removed` field.
        """
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)

        if db_field.name == 'is_removed':
            formfield.help_text = 'Whether this record is soft-deleted. Soft-deleted records ' \
                'are not used but may be re-enabled if needed.'

        return formfield
