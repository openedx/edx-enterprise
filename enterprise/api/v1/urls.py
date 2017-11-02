# -*- coding: utf-8 -*-
"""
URL definitions for enterprise api version 1 endpoint.
"""
from __future__ import absolute_import, unicode_literals

from django.conf.urls import include, url

from rest_framework.routers import DefaultRouter

from enterprise.api.v1 import views

router = DefaultRouter()  # pylint: disable=invalid-name
router.register("enterprise_catalogs", views.EnterpriseCustomerCatalogViewSet, 'enterprise-catalogs')
router.register("enterprise-course-enrollment", views.EnterpriseCourseEnrollmentViewSet, 'enterprise-course-enrollment')
router.register("enterprise-customer", views.EnterpriseCustomerViewSet, 'enterprise-customer')
router.register("enterprise-learner", views.EnterpriseCustomerUserViewSet, 'enterprise-learner')
router.register(
    "enterprise-customer-branding",
    views.EnterpriseCustomerBrandingConfigurationViewSet,
    'enterprise-customer-branding',
)
router.register(
    "enterprise-customer-entitlement",
    views.EnterpriseCustomerEntitlementViewSet,
    'enterprise-customer-entitlement',
)
router.register("catalogs", views.EnterpriseCourseCatalogViewSet, 'catalogs')
router.register(
    "enterprise_customer_reporting",
    views.EnterpriseCustomerReportingConfigurationViewSet,
    'enterprise-customer-reporting',
)

urlpatterns = [
    url(
        r'^enroll_user_in_course',
        views.EnterpriseCustomerEnrollUserInCourseRunView.as_view(),
        name='enroll-user-in-course'
    ),
    url(r'^', include(router.urls)),
]
