"""
URL definitions for enterprise api version 1 endpoint.
"""

from rest_framework.routers import DefaultRouter

from django.urls import re_path

from enterprise.api.v1.views import (
    analytics_summary,
    coupon_codes,
    enterprise_catalog_query,
    enterprise_course_enrollment,
    enterprise_customer,
    enterprise_customer_api_credentials,
    enterprise_customer_branding_configuration,
    enterprise_customer_catalog,
    enterprise_customer_invite_key,
    enterprise_customer_reporting,
    enterprise_customer_sso_configuration,
    enterprise_customer_user,
    enterprise_group,
    enterprise_subsidy_fulfillment,
    enterprise_user,
    notifications,
    pending_enterprise_customer_admin_user,
    pending_enterprise_customer_user,
    plotly_auth,
)

router = DefaultRouter()
router.register(
    "enterprise-course-enrollment",
    enterprise_course_enrollment.EnterpriseCourseEnrollmentViewSet,
    'enterprise-course-enrollment',
)
router.register(
    "licensed-enterprise-course-enrollment",
    enterprise_subsidy_fulfillment.LicensedEnterpriseCourseEnrollmentViewSet,
    'licensed-enterprise-course-enrollment'
)
router.register("enterprise-customer", enterprise_customer.EnterpriseCustomerViewSet, 'enterprise-customer')
router.register("enterprise-learner", enterprise_customer_user.EnterpriseCustomerUserViewSet, 'enterprise-learner')
router.register(
    "pending-enterprise-learner",
    pending_enterprise_customer_user.PendingEnterpriseCustomerUserViewSet,
    'pending-enterprise-learner',
)
router.register(
    "pending-enterprise-admin",
    pending_enterprise_customer_admin_user.PendingEnterpriseCustomerAdminUserViewSet,
    'pending-enterprise-admin',
)
router.register(
    "enterprise-customer-branding",
    enterprise_customer_branding_configuration.EnterpriseCustomerBrandingConfigurationViewSet,
    'enterprise-customer-branding',
)
router.register(
    "enterprise_customer_reporting",
    enterprise_customer_reporting.EnterpriseCustomerReportingConfigurationViewSet,
    'enterprise-customer-reporting',
)
router.register(
    "enterprise-customer-invite-key",
    enterprise_customer_invite_key.EnterpriseCustomerInviteKeyViewSet,
    "enterprise-customer-invite-key"
)
router.register(
    "enterprise_catalog_query",
    enterprise_catalog_query.EnterpriseCatalogQueryViewSet,
    "enterprise_catalog_query"
)
router.register(
    "enterprise_customer_catalog",
    enterprise_customer_catalog.EnterpriseCustomerCatalogWriteViewSet,
    "enterprise_customer_catalog"
)
router.register(
    "enterprise_catalogs", enterprise_customer_catalog.EnterpriseCustomerCatalogViewSet, 'enterprise-catalogs'
)
router.register(
    "enterprise_group", enterprise_group.EnterpriseGroupViewSet, 'enterprise-group'
)


urlpatterns = [
    re_path(
        r'^enterprise_customer_catalog/',
        enterprise_customer_catalog.EnterpriseCustomerCatalogWriteViewSet.as_view(
            {'patch': 'partial_update', 'post': 'create'},
        ),
        name='create_or_update'
    ),
    re_path(
        r'enterprise-subsidy-fulfillment/(?P<fulfillment_source_uuid>[A-Za-z0-9-]+)/?$',
        enterprise_subsidy_fulfillment.EnterpriseSubsidyFulfillmentViewSet.as_view({'get': 'retrieve'}),
        name='enterprise-subsidy-fulfillment'
    ),
    re_path(
        r'enterprise-subsidy-fulfillment/(?P<fulfillment_source_uuid>[A-Za-z0-9-]+)/cancel-fulfillment?$',
        enterprise_subsidy_fulfillment.EnterpriseSubsidyFulfillmentViewSet.as_view({'post': 'cancel_enrollment'}),
        name='enterprise-subsidy-fulfillment-cancel-enrollment'
    ),
    re_path(
        r'operator/enterprise-subsidy-fulfillment/unenrolled/?$',
        enterprise_subsidy_fulfillment.EnterpriseSubsidyFulfillmentViewSet.as_view({'get': 'unenrolled'}),
        name='enterprise-subsidy-fulfillment-unenrolled'
    ),
    re_path(
        r'^read_notification$',
        notifications.NotificationReadView.as_view(),
        name='read-notification'
    ),
    re_path(
        r'link_pending_enterprise_users/(?P<enterprise_uuid>[A-Za-z0-9-]+)/?$',
        pending_enterprise_customer_user.PendingEnterpriseCustomerUserEnterpriseAdminViewSet.as_view(
            {'post': 'link_learners'}
        ),
        name='link-pending-enterprise-learner'
    ),
    re_path(
        r'^request_codes$',
        coupon_codes.CouponCodesView.as_view(),
        name='request-codes'
    ),
    re_path(
        r'^plotly_token/(?P<enterprise_uuid>[A-Za-z0-9-]+)$',
        plotly_auth.PlotlyAuthView.as_view(),
        name='plotly-token'
    ),
    re_path(
        r'^enterprise_report_types/(?P<enterprise_uuid>[A-Za-z0-9-]+)$',
        enterprise_customer_reporting.EnterpriseCustomerReportTypesView.as_view(),
        name='enterprise-report-types'
    ),
    re_path(
        r'^enterprise-customer-branding/update-branding/(?P<enterprise_uuid>[A-Za-z0-9-]+)/$',
        enterprise_customer_branding_configuration.EnterpriseCustomerBrandingConfigurationViewSet.as_view(
            {'patch': 'update_branding'}
        ),
        name='enterprise-customer-update-branding',
    ),
    re_path(
        r'^analytics-summary/(?P<enterprise_uuid>[A-Za-z0-9-]+)$',
        analytics_summary.AnalyticsSummaryView.as_view(),
        name='analytics-summary'
    ),
    re_path(
        r'^enterprise-customer-api-credentials/(?P<enterprise_uuid>[A-Za-z0-9-]+)/regenerate_credentials$',
        enterprise_customer_api_credentials.APICredentialsRegenerateViewSet.as_view(
            {'put': 'update'}
        ),
        name='regenerate-api-credentials'
    ),
    re_path(
        r'^enterprise-customer-api-credentials/(?P<enterprise_uuid>[A-Za-z0-9-]+)/$',
        enterprise_customer_api_credentials.APICredentialsViewSet.as_view(
            {'get': 'retrieve', 'delete': 'destroy', 'put': 'update', 'post': 'create'}
        ),
        name='enterprise-customer-api-credentials'
    ),
    re_path(
        r'^enterprise_customer_sso_configuration/(?P<configuration_uuid>[A-Za-z0-9-]+)/sso_orchestration_complete/?$',
        enterprise_customer_sso_configuration.EnterpriseCustomerSsoConfigurationViewSet.as_view(
            {'post': 'oauth_orchestration_complete'}
        ),
        name='enterprise-customer-sso-configuration-orchestration-complete'
    ),
    re_path(
        r'^enterprise_customer_sso_configuration/(?P<configuration_uuid>[A-Za-z0-9-]+)/?$',
        enterprise_customer_sso_configuration.EnterpriseCustomerSsoConfigurationViewSet.as_view(
            {'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}
        ),
        name='enterprise-customer-sso-configuration'
    ),
    re_path(
        r'^enterprise_customer_sso_configuration/?$',
        enterprise_customer_sso_configuration.EnterpriseCustomerSsoConfigurationViewSet.as_view(
            {'get': 'list', 'post': 'create'}
        ),
        name='enterprise-customer-sso-configuration-base'
    ),
    re_path(
        r'^enterprise-group/(?P<group_uuid>[A-Za-z0-9-]+)/learners/?$',
        enterprise_group.EnterpriseGroupViewSet.as_view(
            {'get': 'get_learners', 'patch': 'update_pending_learner_status'}
        ),
        name='enterprise-group-learners'
    ),
    re_path(
        r'^enterprise_group/(?P<group_uuid>[A-Za-z0-9-]+)/assign_learners/?$',
        enterprise_group.EnterpriseGroupViewSet.as_view({'post': 'assign_learners'}),
        name='enterprise-group-assign-learners'
    ),
    re_path(
        r'^enterprise_group/(?P<group_uuid>[A-Za-z0-9-]+)/remove_learners/?$',
        enterprise_group.EnterpriseGroupViewSet.as_view({'post': 'remove_learners'}),
        name='enterprise-group-remove-learners'
    ),
    re_path(
        r'^enterprise-user/(?P<enterprise_uuid>[A-Za-z0-9-]+)$',
        enterprise_user.EnterpriseUserViewSet.as_view(
            {'get': 'retrieve'}
        ),
        name='enterprise-user'
    ),
]

urlpatterns += router.urls
