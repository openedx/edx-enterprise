"""
URL definitions for enterprise api version 1 endpoint.
"""
from __future__ import absolute_import, unicode_literals

from rest_framework.routers import DefaultRouter

from enterprise.api.v1 import views

router = DefaultRouter()  # pylint: disable=invalid-name
router.register("site", views.SiteViewSet, 'site')
router.register("auth-user", views.UserViewSet, 'auth-user')
router.register("enterprise-customer-catalog", views.EnterpriseCustomerCatalogViewSet, 'enterprise-customer-catalog')
router.register("enterprise-catalogs", views.EnterpriseCustomerCatalogApiViewSet, 'enterprise-catalogs')
# Since Programs is under the umbrella of the course discovery service's common search endpoint,
# we can delegate our Programs endpoint to the view set that uses that search endpoint.
router.register("programs", views.EnterpriseCustomerCatalogApiViewSet, 'programs')
router.register("enterprise-course-enrollment", views.EnterpriseCourseEnrollmentViewSet, 'enterprise-course-enrollment')
router.register("enterprise-customer", views.EnterpriseCustomerViewSet, 'enterprise-customer')
router.register("enterprise-learner", views.EnterpriseCustomerUserViewSet, 'enterprise-learner')
router.register("user-data-sharing-consent", views.UserDataSharingConsentAuditViewSet, 'user-data-sharing-consent')
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
