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
from django.utils.decorators import method_decorator

from enterprise import models
from enterprise.api.filters import EnterpriseCustomerUserFilterBackend
from enterprise.api.pagination import get_paginated_response
from enterprise.api.permissions import IsServiceUserOrReadOnly, IsStaffUserOrLinkedToEnterprise
from enterprise.api.throttles import ServiceUserThrottle
from enterprise.api.v1 import decorators, serializers
from enterprise.course_discovery_api import CatalogsApiClient, ProgramsApiClient

LOGGER = getLogger(__name__)


class EnterpriseViewSet(object):
    """
    Base class for all Enterprise view sets.
    """

    permission_classes = (permissions.IsAuthenticated,)
    authentication_classes = (JwtAuthentication, BearerAuthentication, SessionAuthentication,)
    throttle_classes = (ServiceUserThrottle,)

    def ensure_data_exists(self, request, data, error_message=None):
        """
        Ensure that the wrapped API client's response brings us valid data. If not, raise an error and log it.
        """
        error_message = error_message or ("Unable to fetch API response from "
                                          "endpoint '{}'.".format(request.get_full_path()))
        if not data:
            LOGGER.error(error_message)
            raise NotFound(error_message)


class EnterpriseWrapperApiViewSet(EnterpriseViewSet, viewsets.ViewSet):
    """
    Base class for attribute and method definitions common to all view sets which wrap external APIs.
    """
    pass


class EnterpriseModelViewSet(EnterpriseViewSet):
    """
    Base class for attribute and method definitions common to all view sets.
    """

    filter_backends = (filters.OrderingFilter, filters.DjangoFilterBackend)


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
    API views for the ``enterprise-customer`` endpoint.
    """

    queryset = models.EnterpriseCustomer.active_customers.all()
    serializer_class = serializers.EnterpriseCustomerSerializer

    FIELDS = (
        'uuid', 'name', 'catalog', 'active', 'site', 'enable_data_sharing_consent',
        'enforce_data_sharing_consent',
    )
    filter_fields = FIELDS
    ordering_fields = FIELDS

    @detail_route(
        permission_classes=[permissions.IsAuthenticated, IsServiceUserOrReadOnly, IsStaffUserOrLinkedToEnterprise],
        authentication_classes=[JwtAuthentication, BearerAuthentication, SessionAuthentication],
        throttle_classes=[ServiceUserThrottle],
    )  # pylint: disable=invalid-name,unused-argument
    def courses(self, request, pk=None):
        """
        Retrieve the list of courses contained within the catalog linked to this enterprise.

        Only courses with active course runs are returned. A course run is considered active if it is currently
        open for enrollment, or will open in the future.
        ---
        serializer: serializers.CourseSerializerExcludingClosedRuns
        """
        enterprise_customer = self.get_object()
        self.check_object_permissions(request, enterprise_customer)
        self.ensure_data_exists(
            request,
            enterprise_customer.catalog,
            "No catalog is associated with Enterprise {enterprise_name} from endpoint '{path}'.".format(
                enterprise_name=enterprise_customer.name,
                path=request.get_full_path()
            )
        )

        # We have handled potential error cases and are now ready to call out to the Catalog API.
        catalogs_api = CatalogsApiClient(request.user)
        courses = catalogs_api.get_paginated_catalog_courses(enterprise_customer.catalog, request.GET)

        # An empty response means that there was a problem fetching data from Catalog API, since
        # a Catalog with no courses has a non empty response indicating that there are no courses.
        self.ensure_data_exists(
            request,
            courses,
            "Unable to fetch API response for catalog courses for Enterprise {enterprise_name} from endpoint "
            "'{path}'.".format(
                enterprise_name=enterprise_customer.name,
                path=request.get_full_path()
            )
        )

        serializer = serializers.EnterpriseCoursesReadOnlySerializer(courses)

        # Add enterprise related context for the courses.
        serializer.update_enterprise_courses(enterprise_customer, catalog_id=enterprise_customer.catalog)
        return get_paginated_response(serializer.data, request)


class EnterpriseCourseEnrollmentViewSet(EnterpriseReadWriteModelViewSet):
    """
    API views for the ``enterprise-course-enrollment`` endpoint.
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
    API views for the ``site`` endpoint.
    """

    queryset = Site.objects.all()
    serializer_class = serializers.SiteSerializer

    FIELDS = ('domain', 'name', )
    filter_fields = FIELDS
    ordering_fields = FIELDS


class UserViewSet(EnterpriseReadOnlyModelViewSet):
    """
    API views for the ``auth-user`` endpoint.
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
    API views for the ``enterprise-learner`` endpoint.
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
    API views for the ``enterprise-customer-branding`` endpoint.
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
    API views for the ``user-data-sharing-consent`` endpoint.
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
    API views for the ``enterprise-customer-entitlement`` endpoint.
    """

    queryset = models.EnterpriseCustomerEntitlement.objects.all()
    serializer_class = serializers.EnterpriseCustomerEntitlementSerializer

    FIELDS = (
        'enterprise_customer', 'entitlement_id',
    )
    filter_fields = FIELDS
    ordering_fields = FIELDS


class EnterpriseCatalogViewSet(EnterpriseWrapperApiViewSet):
    """
    API views for the Enterprise's wrapped Course Discovery API ``catalogs`` endpoint.
    """

    serializer_class = serializers.EnterpriseCourseCatalogReadOnlySerializer

    def retrieve(self, request, pk=None):  # pylint: disable=invalid-name
        """
        DRF view to get catalog details.

        Arguments:
            request (HttpRequest): Current request.
            pk (int): Course catalog identifier.

        Returns:
            (Response): DRF response object containing course catalogs.
        """
        catalogs_api = CatalogsApiClient(request.user)
        catalog = catalogs_api.get_catalog(pk)
        self.ensure_data_exists(request, catalog)
        serializer = self.serializer_class(catalog)
        return Response(serializer.data)

    def list(self, request):
        """
        DRF view to list all catalogs.

        Arguments:
            request (HttpRequest): Current request.

        Returns:
            (Response): DRF response object containing course catalogs.
        """
        catalogs_api = CatalogsApiClient(request.user)
        catalogs = catalogs_api.get_paginated_catalogs(request.GET)
        self.ensure_data_exists(request, catalogs)
        serializer = serializers.ResponsePaginationSerializer(catalogs)
        return get_paginated_response(serializer.data, request)

    @method_decorator(decorators.enterprise_customer_required)
    @detail_route()
    def courses(self, request, enterprise_customer, pk=None):  # pylint: disable=invalid-name
        """
        Retrieve the list of courses contained within this catalog.

        Only courses with active course runs are returned. A course run is considered active if it is currently
        open for enrollment, or will open in the future.
        """
        catalogs_api = CatalogsApiClient(request.user)
        courses = catalogs_api.get_paginated_catalog_courses(pk, request.GET)
        self.ensure_data_exists(request, courses)
        serializer = serializers.EnterpriseCoursesReadOnlySerializer(courses)

        # Add enterprise related context for the courses.
        serializer.update_enterprise_courses(enterprise_customer, catalog_id=pk)
        return get_paginated_response(serializer.data, request)


class EnterpriseProgramsViewSet(EnterpriseWrapperApiViewSet):
    """
    API views for the Enterprise's wrapped Course Discovery API ``programs`` endpoint.
    """

    serializer_class = serializers.EnterpriseProgramsReadOnlySerializer

    def retrieve(self, request, uuid=None):  # pylint: disable=invalid-name
        """
        DRF view to get programs.

        Arguments:
            request (HttpRequest): Current request.
            uuid (str): Programs identifier.

        Returns:
            (Response): DRF response object containing a Program.
        """
        programs_api = ProgramsApiClient(request.user)
        program = programs_api.get_program_by_uuid(uuid)
        self.ensure_data_exists(request, program)
        serializer = self.serializer_class(program)
        # Add/remove related/unrelated Enterprise context.
        serializer.update_program_results()
        return Response(serializer.data)

    def list(self, request):
        """
        DRF view to list all programs.

        Arguments:
            request (HttpRequest): Current request

        Returns:
            (Response): DRF response object containing a list of Programs.
        """
        programs_api = ProgramsApiClient(request.user)
        programs = programs_api.get_paginated_programs(request.GET)
        self.ensure_data_exists(request, programs)
        serializer = serializers.EnterprisePaginatedProgramsReadOnlySerializer(programs)
        # Add/remove related/unrelated Enterprise context.
        serializer.update_program_list_results()
        return get_paginated_response(serializer.data, request)
