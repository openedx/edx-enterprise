"""
Views for enterprise api version 1 endpoint.
"""
from __future__ import absolute_import, unicode_literals

from logging import getLogger

from edx_rest_framework_extensions.authentication import BearerAuthentication, JwtAuthentication
from rest_framework import filters, permissions, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import detail_route
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from django.contrib.auth.models import User
from django.contrib.sites.models import Site

from enterprise import models
from enterprise.api.filters import EnterpriseCustomerUserFilterBackend
from enterprise.api.pagination import get_paginated_response
from enterprise.api.permissions import IsServiceUserOrReadOnly
from enterprise.api.throttles import ServiceUserThrottle
from enterprise.api.v1 import serializers
from enterprise.course_catalog_api import CourseCatalogApiClient

logger = getLogger(__name__)  # pylint: disable=invalid-name


class EnterpriseModelViewSet(object):
    """
    Base class for attribute and method definitions common to all view sets.
    """
    filter_backends = (filters.OrderingFilter, filters.DjangoFilterBackend)
    permission_classes = (permissions.IsAuthenticated,)
    authentication_classes = (JwtAuthentication, BearerAuthentication, SessionAuthentication,)
    throttle_classes = (ServiceUserThrottle,)


class EnterpriseReadOnlyModelViewSet(EnterpriseModelViewSet, viewsets.ReadOnlyModelViewSet):
    """
    Base class for all read only Enterprise model view sets.
    """
    pass


class EnterpriseReadWriteModelViewSet(EnterpriseModelViewSet, viewsets.ModelViewSet):
    """
    Base class for all read/write Enterprise model view sets.
    """
    permission_classes = (permissions.IsAuthenticated, IsServiceUserOrReadOnly,)


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


class EnterpriseCourseEnrollmentViewSet(EnterpriseReadWriteModelViewSet):
    """
    API views for `enterprise course enrollment` api endpoint.
    """
    queryset = models.EnterpriseCourseEnrollment.objects.all()

    FIELDS = (
        'enterprise_customer_user', 'consent_granted', 'course_id'
    )
    filter_fields = FIELDS
    ordering_fields = FIELDS

    def get_serializer_class(self):
        """
        Use a special serializer for any requests that aren't read-only.
        """
        if self.request.method in ('GET', ):
            return serializers.EnterpriseCourseEnrollmentReadOnlySerializer
        return serializers.EnterpriseCourseEnrollmentWriteSerializer


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


class EnterpriseCustomerUserViewSet(EnterpriseReadWriteModelViewSet):
    """
    API views for `enterprise customer user` api endpoint.
    """
    queryset = models.EnterpriseCustomerUser.objects.all()
    filter_backends = (filters.OrderingFilter, filters.DjangoFilterBackend, EnterpriseCustomerUserFilterBackend)

    FIELDS = (
        'enterprise_customer', 'user_id',
    )
    filter_fields = FIELDS
    ordering_fields = FIELDS

    def get_serializer_class(self):
        """
        Use a flat serializer for any requests that aren't read-only.
        """
        if self.request.method in ('GET', ):
            return serializers.EnterpriseCustomerUserReadOnlySerializer
        return serializers.EnterpriseCustomerUserWriteSerializer

    @detail_route()
    def entitlements(self, request, pk=None):  # pylint: disable=invalid-name,unused-argument
        """
        Retrieve the list of entitlements available to this learner.

        Only those entitlements are returned that satisfy enterprise customer's data sharing setting.

        Arguments:
            request (HttpRequest): Reference to in progress request instance.
            pk (Int): Primary key value of the selected enterprise learner.

        Returns:
            (HttpResponse): Response object containing a list of learner's entitlements.
        """
        enterprise_customer_user = self.get_object()

        instance = {"entitlements": enterprise_customer_user.entitlements}
        serializer = serializers.EnterpriseCustomerUserEntitlementSerializer(instance, context={'request': request})
        return Response(serializer.data)


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


class EnterpriseCatalogViewSet(viewsets.ViewSet):
    """
    API views for `enterprise customer catalogs` api endpoint.
    """
    serializer_class = serializers.EnterpriseCourseCatalogReadOnlySerializer
    permission_classes = (permissions.IsAuthenticated,)
    authentication_classes = (JwtAuthentication, BearerAuthentication, SessionAuthentication,)
    throttle_classes = (ServiceUserThrottle,)

    def list(self, request):
        """
        DRF view to list all catalogs.

        Arguments:
            request (HttpRequest): Current request

        Returns:
            (Response): DRF response object containing course catalogs.
        """
        # fetch all course catalogs.
        catalog_api = CourseCatalogApiClient(request.user)
        catalogs = catalog_api.get_all_catalogs()
        serializer = self.serializer_class(catalogs, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):  # pylint: disable=invalid-name
        """
        DRF view to get catalog details.

        Arguments:
            request (HttpRequest): Current request
            pk (int): Course catalog identifier

        Returns:
            (Response): DRF response object containing course catalogs.
        """
        # fetch course catalog for the given catalog id.
        catalog_api = CourseCatalogApiClient(request.user)
        catalog = catalog_api.get_catalog(pk)

        if not catalog:
            logger.error("Unable to fetch API response for given catalog from endpoint '/catalog/%s/'.", pk)
            raise NotFound("The resource you are looking for does not exist.")

        serializer = self.serializer_class(catalog)
        return Response(serializer.data)

    @detail_route()
    def courses(self, request, pk=None):  # pylint: disable=invalid-name
        """
        Retrieve the list of courses contained within this catalog.

        Only courses with active course runs are returned. A course run is considered active if it is currently
        open for enrollment, or will open in the future.
        ---
        serializer: serializers.CourseSerializerExcludingClosedRuns
        """
        page = request.GET.get('page', 1)
        catalog_api = CourseCatalogApiClient(request.user)
        courses = catalog_api.get_paginated_catalog_courses(pk, page)

        # if API returned an empty response, that means pagination has ended.
        # An empty response can also means that there was a problem fetching data from catalog API.
        if not courses:
            logger.error(
                "Unable to fetch API response for catalog courses from endpoint '/catalog/%s/courses?page=%s'.",
                pk, page,
            )
            raise NotFound("The resource you are looking for does not exist.")

        serializer = serializers.EnterpriseCatalogCoursesReadOnlySerializer(courses)

        # Add enterprise related context for the courses.
        serializer.update_enterprise_courses(request, pk)
        return get_paginated_response(serializer.data, request)
