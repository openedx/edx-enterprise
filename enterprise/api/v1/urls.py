# -*- coding: utf-8 -*-
"""
URL definitions for enterprise api version 1 endpoint.
"""

from rest_framework.routers import DefaultRouter

from django.conf.urls import url

from enterprise.api.v1 import views

router = DefaultRouter()  # pylint: disable=invalid-name
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

urlpatterns = [
    url(
        r'^enterprise_catalog_query/(?P<catalog_query_id>[\d]+)/$',
        views.CatalogQueryView.as_view(),
        name='enterprise-catalog-query'
    ),
    url(
        r'^request_codes$',
        views.CouponCodesView.as_view(),
        name='request-codes'
    ),
    url(
        r'^tableau_token$',
        views.TableauAuthViewSet.as_view(),
        name='tableau-token'
    ),
]

urlpatterns += router.urls
