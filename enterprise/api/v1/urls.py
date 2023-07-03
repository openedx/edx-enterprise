"""
URL definitions for enterprise api version 1 endpoint.
"""

from rest_framework.routers import DefaultRouter

from django.urls import re_path

from enterprise.api.v1.views import (
    coupon_codes,
    enterprise_catalog_query,
    enterprise_course_enrollment,
    enterprise_customer,
    enterprise_customer_branding_configuration,
    enterprise_customer_catalog,
    enterprise_customer_invite_key,
    enterprise_customer_reporting,
    enterprise_customer_user,
    enterprise_subsidy_fulfillment,
    notifications,
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


urlpatterns = [
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
        name='enterprise-customer-update-branding')
]

urlpatterns += router.urls
