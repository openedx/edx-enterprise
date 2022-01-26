"""
URL definitions for enterprise api version 1 endpoint.
"""

from rest_framework.routers import DefaultRouter

from django.urls import re_path

from enterprise.api.v1 import views

router = DefaultRouter()
router.register("enterprise_catalogs", views.EnterpriseCustomerCatalogViewSet, 'enterprise-catalogs')
router.register("enterprise-course-enrollment", views.EnterpriseCourseEnrollmentViewSet, 'enterprise-course-enrollment')
router.register(
    "licensed-enterprise-course-enrollment",
    views.LicensedEnterpriseCourseEnrollmentViewSet,
    'licensed-enterprise-course-enrollment'
)
router.register("enterprise-customer", views.EnterpriseCustomerViewSet, 'enterprise-customer')
router.register("enterprise-learner", views.EnterpriseCustomerUserViewSet, 'enterprise-learner')
router.register("pending-enterprise-learner", views.PendingEnterpriseCustomerUserViewSet, 'pending-enterprise-learner')
router.register(
    "enterprise-customer-branding",
    views.EnterpriseCustomerBrandingConfigurationViewSet,
    'enterprise-customer-branding',
)
router.register(
    "enterprise_customer_reporting",
    views.EnterpriseCustomerReportingConfigurationViewSet,
    'enterprise-customer-reporting',
)
router.register(
    "enterprise-customer-invite-key",
    views.EnterpriseCustomerInviteKeyViewSet,
    "enterprise-customer-invite-key"
)

urlpatterns = [
    re_path(r'^read_notification$', views.NotificationReadView.as_view(),
            name='read-notification'
            ),
    re_path(
        r'link_pending_enterprise_users/(?P<enterprise_uuid>[A-Za-z0-9-]+)/?$',
        views.PendingEnterpriseCustomerUserEnterpriseAdminViewSet.as_view({'post': 'link_learners'}),
        name='link-pending-enterprise-learner'
    ),
    re_path(
        r'^enterprise_catalog_query/(?P<catalog_query_id>[\d]+)/$',
        views.CatalogQueryView.as_view(),
        name='enterprise-catalog-query'
    ),
    re_path(r'^request_codes$', views.CouponCodesView.as_view(),
            name='request-codes'
            ),
    re_path(
        r'^tableau_token/(?P<enterprise_uuid>[A-Za-z0-9-]+)$',
        views.TableauAuthView.as_view(),
        name='tableau-token'
    ),
    re_path(
        r'^enterprise_report_types/(?P<enterprise_uuid>[A-Za-z0-9-]+)$',
        views.EnterpriseCustomerReportTypesView.as_view(),
        name='enterprise-report-types'
    ),
]

urlpatterns += router.urls
