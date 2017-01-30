"""
Views for enterprise api version 1 endpoint.
"""
from __future__ import absolute_import, unicode_literals

from edx_rest_framework_extensions.authentication import BearerAuthentication, JwtAuthentication
from rest_framework import filters, permissions, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework_oauth.authentication import OAuth2Authentication

from django.contrib.auth.models import User
from django.contrib.sites.models import Site

from enterprise import models
from enterprise.api.filters import EnterpriseCustomerUserFilterBackend
from enterprise.api.throttles import ServiceUserThrottle
from enterprise.api.v1 import serializers


class EnterpriseReadOnlyModelViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Base class for attribute and method definitions common to all view sets.
    """
    filter_backends = (filters.OrderingFilter, filters.DjangoFilterBackend)
    permission_classes = (permissions.IsAuthenticated,)
    authentication_classes = (OAuth2Authentication, SessionAuthentication, BearerAuthentication, JwtAuthentication)
    throttle_classes = (ServiceUserThrottle,)


class EnterpriseCustomerViewSet(EnterpriseReadOnlyModelViewSet):
    """
    API views for `enterprise customer` api endpoint.
    """
    queryset = models.EnterpriseCustomer.active_customers.all()
    serializer_class = serializers.EnterpriseCustomerSerializer

    FIELDS = (
        'uuid', 'name', 'catalog', 'active', 'site', 'enable_data_sharing_consent',
        'enforce_data_sharing_consent',
    )
    filter_fields = FIELDS
    ordering_fields = FIELDS


class SiteViewSet(EnterpriseReadOnlyModelViewSet):
    """
    API views for `site` api endpoint.
    """
    queryset = Site.objects.all()
    serializer_class = serializers.SiteSerializer

    FIELDS = ('domain', 'name', )
    filter_fields = FIELDS
    ordering_fields = FIELDS


class UserViewSet(EnterpriseReadOnlyModelViewSet):
    """
    API views for `user` api endpoint.
    """
    queryset = User.objects.all()
    serializer_class = serializers.UserSerializer

    FIELDS = (
        'username', 'first_name', 'last_name', 'email', 'is_staff', 'is_active'
    )
    filter_fields = FIELDS
    ordering_fields = FIELDS


class EnterpriseCustomerUserViewSet(EnterpriseReadOnlyModelViewSet):
    """
    API views for `enterprise customer user` api endpoint.
    """
    queryset = models.EnterpriseCustomerUser.objects.all()
    serializer_class = serializers.EnterpriseCustomerUserSerializer
    filter_backends = (filters.OrderingFilter, filters.DjangoFilterBackend, EnterpriseCustomerUserFilterBackend)

    FIELDS = (
        'enterprise_customer', 'user_id',
    )
    filter_fields = FIELDS
    ordering_fields = FIELDS


class EnterpriseCustomerBrandingConfigurationViewSet(EnterpriseReadOnlyModelViewSet):
    """
    API views for `enterprise customer branding` api endpoint.
    """
    queryset = models.EnterpriseCustomerBrandingConfiguration.objects.all()
    serializer_class = serializers.EnterpriseCustomerBrandingConfigurationSerializer

    FIELDS = (
        'enterprise_customer',
    )
    filter_fields = FIELDS
    ordering_fields = FIELDS


class UserDataSharingConsentAuditViewSet(EnterpriseReadOnlyModelViewSet):
    """
    API views for `user data sharing consent` api endpoint.
    """
    queryset = models.UserDataSharingConsentAudit.objects.all()
    serializer_class = serializers.UserDataSharingConsentAuditSerializer

    FIELDS = (
        'user', 'state',
    )
    filter_fields = FIELDS
    ordering_fields = FIELDS


class EnterpriseCustomerEntitlementViewSet(EnterpriseReadOnlyModelViewSet):
    """
    API views for `enterprise customer entitlements` api endpoint.
    """
    queryset = models.EnterpriseCustomerEntitlement.objects.all()
    serializer_class = serializers.EnterpriseCustomerEntitlementSerializer

    FIELDS = (
        'enterprise_customer', 'entitlement_id',
    )
    filter_fields = FIELDS
    ordering_fields = FIELDS
