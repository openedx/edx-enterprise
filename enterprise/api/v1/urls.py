"""
URL definitions for enterprise api version 1 endpoint.
"""
from __future__ import absolute_import, unicode_literals

from rest_framework.routers import DefaultRouter

from enterprise.api.v1 import views

# Pylint considers module level variable as "Constant" and expects them to be upper-cased
# that is why we have disabled 'invalid-name' check for variable definition below.
router = DefaultRouter()  # pylint: disable=invalid-name
router.register("site", views.SiteViewSet, 'site')
router.register("auth-user", views.UserViewSet, 'auth-user')
router.register(
    "enterprise-course-enrollment",
    views.EnterpriseCourseEnrollmentViewSet,
    'enterprise-course-enrollment'
)
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
router.register("catalogs", views.EnterpriseCatalogViewSet, 'catalogs')
