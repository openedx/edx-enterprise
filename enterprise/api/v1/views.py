# -*- coding: utf-8 -*-
"""
Views for enterprise api version 1 endpoint.
"""
from __future__ import absolute_import, unicode_literals

from logging import getLogger
from smtplib import SMTPException

from edx_rbac.decorators import permission_required
from edx_rest_framework_extensions.auth.bearer.authentication import BearerAuthentication
from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from rest_framework import filters, permissions, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import detail_route, list_route
from rest_framework.exceptions import NotFound
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST, HTTP_500_INTERNAL_SERVER_ERROR
from rest_framework.views import APIView
from rest_framework_xml.renderers import XMLRenderer
from six.moves.urllib.parse import quote_plus, unquote  # pylint: disable=import-error,ungrouped-imports

from django.apps import apps
from django.conf import settings
from django.core import mail
from django.http import Http404
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _

from enterprise import models
from enterprise.api.filters import EnterpriseCustomerUserFilterBackend, UserFilterBackend
from enterprise.api.pagination import get_paginated_response
from enterprise.api.throttles import ServiceUserThrottle
from enterprise.api.utils import get_enterprise_customer_from_catalog_id
from enterprise.api.v1 import serializers
from enterprise.api.v1.decorators import enterprise_customer_required, require_at_least_one_query_parameter
from enterprise.api.v1.permissions import (
    HasEnterpriseDataAPIAccess,
    HasEnterpriseEnrollmentAPIAccess,
    IsInEnterpriseGroup,
)
from enterprise.api_client.discovery import CourseCatalogApiClient
from enterprise.constants import COURSE_KEY_URL_PATTERN
from enterprise.errors import CodesAPIRequestError
from enterprise.utils import get_request_value

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
        if not data:
            error_message = (
                error_message or "Unable to fetch API response from endpoint '{}'.".format(request.get_full_path())
            )
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

    filter_backends = (filters.OrderingFilter, filters.DjangoFilterBackend, UserFilterBackend,)
    permission_classes = (permissions.IsAuthenticated, permissions.DjangoModelPermissions,)
    USER_ID_FILTER = 'id'


class EnterpriseReadOnlyModelViewSet(EnterpriseModelViewSet, viewsets.ReadOnlyModelViewSet):
    """
    Base class for all read only Enterprise model view sets.
    """
    pass


class EnterpriseReadWriteModelViewSet(EnterpriseModelViewSet, viewsets.ModelViewSet):
    """
    Base class for all read/write Enterprise model view sets.
    """

    permission_classes = (permissions.IsAuthenticated, permissions.DjangoModelPermissions,)


class EnterpriseCustomerViewSet(EnterpriseReadWriteModelViewSet):
    """
    API views for the ``enterprise-customer`` API endpoint.
    """

    queryset = models.EnterpriseCustomer.active_customers.all()
    serializer_class = serializers.EnterpriseCustomerSerializer

    USER_ID_FILTER = 'enterprise_customer_users__user_id'
    FIELDS = (
        'uuid', 'slug', 'name', 'catalog', 'active', 'site', 'enable_data_sharing_consent',
        'enforce_data_sharing_consent',
    )
    filter_fields = FIELDS
    ordering_fields = FIELDS

    @method_decorator(require_at_least_one_query_parameter('course_run_ids', 'program_uuids'))
    @detail_route()
    @permission_required('enterprise.can_view_catalog', fn=lambda request, pk, course_run_ids, program_uuids: pk)
    # pylint: disable=invalid-name,unused-argument
    def contains_content_items(self, request, pk, course_run_ids, program_uuids):
        """
        Return whether or not the specified content is available to the EnterpriseCustomer.

        Multiple course_run_ids and/or program_uuids query parameters can be sent to this view to check
        for their existence in the EnterpriseCustomerCatalogs associated with this EnterpriseCustomer.
        At least one course run key or program UUID value must be included in the request.
        """
        enterprise_customer = self.get_object()

        # Maintain plus characters in course key.
        course_run_ids = [unquote(quote_plus(course_run_id)) for course_run_id in course_run_ids]

        contains_content_items = False
        for catalog in enterprise_customer.enterprise_customer_catalogs.all():
            contains_course_runs = not course_run_ids or catalog.contains_courses(course_run_ids)
            contains_program_uuids = not program_uuids or catalog.contains_programs(program_uuids)
            if contains_course_runs and contains_program_uuids:
                contains_content_items = True
                break

        return Response({'contains_content_items': contains_content_items})

    @detail_route()
    @permission_required('enterprise.can_view_catalog', fn=lambda request, pk: pk)
    def courses(self, request, pk=None):  # pylint: disable=invalid-name,unused-argument
        """
        Retrieve the list of courses contained within the catalog linked to this enterprise.

        Only courses with active course runs are returned. A course run is considered active if it is currently
        open for enrollment, or will open in the future.
        """
        enterprise_customer = self.get_object()
        self.check_object_permissions(request, enterprise_customer)
        self.ensure_data_exists(
            request,
            enterprise_customer.catalog,
            error_message="No catalog is associated with Enterprise {enterprise_name} from endpoint '{path}'.".format(
                enterprise_name=enterprise_customer.name,
                path=request.get_full_path()
            )
        )

        # We have handled potential error cases and are now ready to call out to the Catalog API.
        catalog_api = CourseCatalogApiClient(request.user, enterprise_customer.site)
        courses = catalog_api.get_paginated_catalog_courses(enterprise_customer.catalog, request.GET)

        # An empty response means that there was a problem fetching data from Catalog API, since
        # a Catalog with no courses has a non empty response indicating that there are no courses.
        self.ensure_data_exists(
            request,
            courses,
            error_message=(
                "Unable to fetch API response for catalog courses for "
                "Enterprise {enterprise_name} from endpoint '{path}'.".format(
                    enterprise_name=enterprise_customer.name,
                    path=request.get_full_path()
                )
            )
        )

        serializer = serializers.EnterpriseCatalogCoursesReadOnlySerializer(courses)

        # Add enterprise related context for the courses.
        serializer.update_enterprise_courses(enterprise_customer, catalog_id=enterprise_customer.catalog)
        return get_paginated_response(serializer.data, request)

    @detail_route(methods=['post'], permission_classes=[
        permissions.IsAuthenticated,
        HasEnterpriseEnrollmentAPIAccess,
    ])
    @permission_required('enterprise.can_enroll_learners', fn=lambda request, pk: pk)
    # pylint: disable=invalid-name,unused-argument
    def course_enrollments(self, request, pk):
        """
        Creates a course enrollment for an EnterpriseCustomerUser.
        """
        enterprise_customer = self.get_object()
        serializer = serializers.EnterpriseCustomerCourseEnrollmentsSerializer(
            data=request.data,
            many=True,
            context={
                'enterprise_customer': enterprise_customer,
                'request_user': request.user,
            }
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=HTTP_200_OK)

        return Response(serializer.errors, status=HTTP_400_BAD_REQUEST)

    @method_decorator(require_at_least_one_query_parameter('permissions'))
    @list_route(permission_classes=[
        permissions.IsAuthenticated,
        IsInEnterpriseGroup,
    ])
    def with_access_to(self, request, *args, **kwargs):  # pylint: disable=invalid-name,unused-argument
        """
        Returns the list of enterprise customers the user has a specified group permission access to.
        """
        self.queryset = self.queryset.order_by('name')
        enterprise_id = self.request.query_params.get('enterprise_id', None)
        enterprise_slug = self.request.query_params.get('enterprise_slug', None)
        enterprise_name = self.request.query_params.get('search', None)

        if enterprise_id is not None:
            self.queryset = self.queryset.filter(uuid=enterprise_id)
        elif enterprise_slug is not None:
            self.queryset = self.queryset.filter(slug=enterprise_slug)
        elif enterprise_name is not None:
            self.queryset = self.queryset.filter(name__icontains=enterprise_name)
        return self.list(request, *args, **kwargs)

    @list_route()
    @permission_required('enterprise.can_access_admin_dashboard')
    def dashboard_list(self, request, *args, **kwargs):  # pylint: disable=invalid-name,unused-argument
        """
        Supports listing dashboard enterprises for edx-portal frontend.
        """
        self.queryset = self.queryset.order_by('name')
        enterprise_id = self.request.query_params.get('enterprise_id', None)
        enterprise_slug = self.request.query_params.get('enterprise_slug', None)
        enterprise_name = self.request.query_params.get('search', None)

        if enterprise_id is not None:
            self.queryset = self.queryset.filter(uuid=enterprise_id)
        elif enterprise_slug is not None:
            self.queryset = self.queryset.filter(slug=enterprise_slug)
        elif enterprise_name is not None:
            self.queryset = self.queryset.filter(name__icontains=enterprise_name)
        return self.list(request, *args, **kwargs)


class EnterpriseCourseEnrollmentViewSet(EnterpriseReadWriteModelViewSet):
    """
    API views for the ``enterprise-course-enrollment`` API endpoint.
    """

    queryset = models.EnterpriseCourseEnrollment.objects.all()

    USER_ID_FILTER = 'enterprise_customer_user__user_id'
    FIELDS = (
        'enterprise_customer_user', 'course_id'
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


class EnterpriseCustomerUserViewSet(EnterpriseReadWriteModelViewSet):
    """
    API views for the ``enterprise-learner`` API endpoint.
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
            request (HttpRequest): Reference to in-progress request instance.
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
    API views for the ``enterprise-customer-branding`` API endpoint.
    """

    queryset = models.EnterpriseCustomerBrandingConfiguration.objects.all()
    serializer_class = serializers.EnterpriseCustomerBrandingConfigurationSerializer

    USER_ID_FILTER = 'enterprise_customer__enterprise_customer_users__user_id'
    FIELDS = (
        'enterprise_customer__slug',
    )
    filter_fields = FIELDS
    ordering_fields = FIELDS
    lookup_field = 'enterprise_customer__slug'


class EnterpriseCustomerEntitlementViewSet(EnterpriseReadOnlyModelViewSet):
    """
    API views for the ``enterprise-customer-entitlements`` API endpoint.
    """

    queryset = models.EnterpriseCustomerEntitlement.objects.all()
    serializer_class = serializers.EnterpriseCustomerEntitlementSerializer

    USER_ID_FILTER = 'enterprise_customer__enterprise_customer_users__user_id'
    FIELDS = (
        'enterprise_customer', 'entitlement_id',
    )
    filter_fields = FIELDS
    ordering_fields = FIELDS


class EnterpriseCustomerCatalogViewSet(EnterpriseReadOnlyModelViewSet):
    """
    API Views for performing search through course discovery at the ``enterprise_catalogs`` API endpoint.
    """
    queryset = models.EnterpriseCustomerCatalog.objects.all()

    USER_ID_FILTER = 'enterprise_customer__enterprise_customer_users__user_id'
    FIELDS = (
        'uuid', 'enterprise_customer',
    )
    filter_fields = FIELDS
    ordering_fields = FIELDS
    renderer_classes = (JSONRenderer, XMLRenderer,)

    @permission_required('enterprise.can_view_catalog', fn=lambda request, *args, **kwargs: None)
    def list(self, request, *args, **kwargs):
        return super(EnterpriseCustomerCatalogViewSet, self).list(request, *args, **kwargs)

    @permission_required(
        'enterprise.can_view_catalog',
        fn=lambda request, *args, **kwargs: get_enterprise_customer_from_catalog_id(kwargs['pk']))
    def retrieve(self, request, *args, **kwargs):
        return super(EnterpriseCustomerCatalogViewSet, self).retrieve(request, *args, **kwargs)

    def get_serializer_class(self):
        action = getattr(self, 'action', None)
        if action == 'retrieve':
            return serializers.EnterpriseCustomerCatalogDetailSerializer
        return serializers.EnterpriseCustomerCatalogSerializer

    @method_decorator(require_at_least_one_query_parameter('course_run_ids', 'program_uuids'))
    @detail_route()
    # pylint: disable=invalid-name,unused-argument
    def contains_content_items(self, request, pk, course_run_ids, program_uuids):
        """
        Return whether or not the EnterpriseCustomerCatalog contains the specified content.

        Multiple course_run_ids and/or program_uuids query parameters can be sent to this view to check
        for their existence in the EnterpriseCustomerCatalog. At least one course run key
        or program UUID value must be included in the request.
        """
        enterprise_customer_catalog = self.get_object()

        # Maintain plus characters in course key.
        course_run_ids = [unquote(quote_plus(course_run_id)) for course_run_id in course_run_ids]

        contains_content_items = True
        if course_run_ids:
            contains_content_items = enterprise_customer_catalog.contains_courses(course_run_ids)
        if program_uuids:
            contains_content_items = (
                contains_content_items and
                enterprise_customer_catalog.contains_programs(program_uuids)
            )

        return Response({'contains_content_items': contains_content_items})

    @detail_route(url_path='courses/{}'.format(COURSE_KEY_URL_PATTERN))
    @permission_required(
        'enterprise.can_view_catalog',
        fn=lambda request, pk, course_key: get_enterprise_customer_from_catalog_id(pk))
    def course_detail(self, request, pk, course_key):  # pylint: disable=invalid-name,unused-argument
        """
        Return the metadata for the specified course.

        The course needs to be included in the specified EnterpriseCustomerCatalog
        in order for metadata to be returned from this endpoint.
        """
        enterprise_customer_catalog = self.get_object()
        course = enterprise_customer_catalog.get_course(course_key)
        if not course:
            raise Http404

        context = self.get_serializer_context()
        context['enterprise_customer_catalog'] = enterprise_customer_catalog
        serializer = serializers.CourseDetailSerializer(course, context=context)
        return Response(serializer.data)

    @detail_route(url_path='course_runs/{}'.format(settings.COURSE_ID_PATTERN))
    @permission_required(
        'enterprise.can_view_catalog',
        fn=lambda request, pk, course_id: get_enterprise_customer_from_catalog_id(pk))
    def course_run_detail(self, request, pk, course_id):  # pylint: disable=invalid-name,unused-argument
        """
        Return the metadata for the specified course run.

        The course run needs to be included in the specified EnterpriseCustomerCatalog
        in order for metadata to be returned from this endpoint.
        """
        enterprise_customer_catalog = self.get_object()
        course_run = enterprise_customer_catalog.get_course_run(course_id)
        if not course_run:
            raise Http404

        context = self.get_serializer_context()
        context['enterprise_customer_catalog'] = enterprise_customer_catalog
        serializer = serializers.CourseRunDetailSerializer(course_run, context=context)
        return Response(serializer.data)

    @detail_route(url_path='programs/(?P<program_uuid>[^/]+)')
    @permission_required(
        'enterprise.can_view_catalog',
        fn=lambda request, pk, program_uuid: get_enterprise_customer_from_catalog_id(pk))
    def program_detail(self, request, pk, program_uuid):  # pylint: disable=invalid-name,unused-argument
        """
        Return the metadata for the specified program.

        The program needs to be included in the specified EnterpriseCustomerCatalog
        in order for metadata to be returned from this endpoint.
        """
        enterprise_customer_catalog = self.get_object()
        program = enterprise_customer_catalog.get_program(program_uuid)
        if not program:
            raise Http404

        context = self.get_serializer_context()
        context['enterprise_customer_catalog'] = enterprise_customer_catalog
        serializer = serializers.ProgramDetailSerializer(program, context=context)
        return Response(serializer.data)


class EnterpriseCourseCatalogViewSet(EnterpriseWrapperApiViewSet):
    """
    API views for the ``catalogs`` API endpoint.
    """

    serializer_class = serializers.CourseCatalogApiResponseReadOnlySerializer

    def list(self, request):
        """
        DRF view to list all catalogs.

        Arguments:
            request (HttpRequest): Current request

        Returns:
            (Response): DRF response object containing course catalogs.
        """
        catalog_api = CourseCatalogApiClient(request.user)
        catalogs = catalog_api.get_paginated_catalogs(request.GET)
        self.ensure_data_exists(request, catalogs)
        serializer = serializers.ResponsePaginationSerializer(catalogs)
        return get_paginated_response(serializer.data, request)

    def retrieve(self, request, pk=None):  # pylint: disable=invalid-name
        """
        DRF view to get catalog details.

        Arguments:
            request (HttpRequest): Current request
            pk (int): Course catalog identifier

        Returns:
            (Response): DRF response object containing course catalogs.
        """
        catalog_api = CourseCatalogApiClient(request.user)
        catalog = catalog_api.get_catalog(pk)
        self.ensure_data_exists(
            request,
            catalog,
            error_message=(
                "Unable to fetch API response for given catalog from endpoint '/catalog/{pk}/'. "
                "The resource you are looking for does not exist.".format(pk=pk)
            )
        )
        serializer = self.serializer_class(catalog)
        return Response(serializer.data)

    @method_decorator(enterprise_customer_required)
    @detail_route()
    def courses(self, request, enterprise_customer, pk=None):  # pylint: disable=invalid-name
        """
        Retrieve the list of courses contained within this catalog.

        Only courses with active course runs are returned. A course run is considered active if it is currently
        open for enrollment, or will open in the future.
        """
        catalog_api = CourseCatalogApiClient(request.user, enterprise_customer.site)
        courses = catalog_api.get_paginated_catalog_courses(pk, request.GET)

        # If the API returned an empty response, that means pagination has ended.
        # An empty response can also mean that there was a problem fetching data from catalog API.
        self.ensure_data_exists(
            request,
            courses,
            error_message=(
                "Unable to fetch API response for catalog courses from endpoint '{endpoint}'. "
                "The resource you are looking for does not exist.".format(endpoint=request.get_full_path())
            )
        )
        serializer = serializers.EnterpriseCatalogCoursesReadOnlySerializer(courses)

        # Add enterprise related context for the courses.
        serializer.update_enterprise_courses(enterprise_customer, catalog_id=pk)
        return get_paginated_response(serializer.data, request)


class EnterpriseCustomerReportingConfigurationViewSet(EnterpriseReadOnlyModelViewSet):
    """
    API views for the ``enterprise-customer-reporting`` API endpoint.
    """

    queryset = models.EnterpriseCustomerReportingConfiguration.objects.all()
    serializer_class = serializers.EnterpriseCustomerReportingConfigurationSerializer

    USER_ID_FILTER = 'enterprise_customer__enterprise_customer_users__user_id'
    FIELDS = (
        'enterprise_customer',
    )
    filter_fields = FIELDS
    ordering_fields = FIELDS


class CouponCodesView(APIView):
    """
    API to request coupon codes.
    """
    permission_classes = (permissions.IsAuthenticated, HasEnterpriseDataAPIAccess)
    authentication_classes = (JwtAuthentication, BearerAuthentication, SessionAuthentication,)
    throttle_classes = (ServiceUserThrottle,)

    REQUIRED_PARAM_EMAIL = 'email'
    REQUIRED_PARAM_ENTERPRISE_NAME = 'enterprise_name'
    OPTIONAL_PARAM_NUMBER_OF_CODES = 'number_of_codes'

    MISSING_REQUIRED_PARAMS_MSG = "Some required parameter(s) missing: {}"

    def get_required_query_params(self, request):
        """
        Gets ``email``, ``enterprise_name``, and ``number_of_codes``,
        which are the relevant parameters for this API endpoint.

        :param request: The request to this endpoint.
        :return: The ``email``, ``enterprise_name``, and ``number_of_codes`` from the request.
        """
        email = get_request_value(request, self.REQUIRED_PARAM_EMAIL, '')
        enterprise_name = get_request_value(request, self.REQUIRED_PARAM_ENTERPRISE_NAME, '')
        number_of_codes = get_request_value(request, self.OPTIONAL_PARAM_NUMBER_OF_CODES, '')
        if not (email and enterprise_name):
            raise CodesAPIRequestError(
                self.get_missing_params_message([
                    (self.REQUIRED_PARAM_EMAIL, bool(email)),
                    (self.REQUIRED_PARAM_ENTERPRISE_NAME, bool(enterprise_name)),
                ])
            )
        return email, enterprise_name, number_of_codes

    def get_missing_params_message(self, parameter_state):
        """
        Get a user-friendly message indicating a missing parameter for the API endpoint.
        """
        params = ', '.join(name for name, present in parameter_state if not present)
        return self.MISSING_REQUIRED_PARAMS_MSG.format(params)

    @permission_required('enterprise.can_access_admin_dashboard')
    def post(self, request):
        """
        POST /enterprise/api/v1/request_codes

        Requires a JSON object of the following format:
        >>> {
        >>>     "email": "bob@alice.com",
        >>>     "enterprise_name": "IBM",
        >>>     "number_of_codes": "50"
        >>> }

        Keys:
        *email*
            Email of the customer who has requested more codes.
        *enterprise_name*
            The name of the enterprise requesting more codes.
        *number_of_codes*
            The number of codes requested.
        """
        try:
            email, enterprise_name, number_of_codes = self.get_required_query_params(request)
        except CodesAPIRequestError as invalid_request:
            return Response({'error': str(invalid_request)}, status=HTTP_400_BAD_REQUEST)

        subject_line = _('Code Management - Request for Codes by {token_enterprise_name}').format(
            token_enterprise_name=enterprise_name
        )
        msg_with_codes = _('{token_email} from {token_enterprise_name} has requested {token_number_codes} additional '
                           'codes. Please reach out to them.').format(
                               token_email=email,
                               token_enterprise_name=enterprise_name,
                               token_number_codes=number_of_codes)
        msg_without_codes = _('{token_email} from {token_enterprise_name} has requested additional codes.'
                              ' Please reach out to them.').format(
                                  token_email=email,
                                  token_enterprise_name=enterprise_name)
        app_config = apps.get_app_config("enterprise")
        from_email_address = app_config.customer_success_email
        cs_email = app_config.customer_success_email
        data = {
            self.REQUIRED_PARAM_EMAIL: email,
            self.REQUIRED_PARAM_ENTERPRISE_NAME: enterprise_name,
            self.OPTIONAL_PARAM_NUMBER_OF_CODES: number_of_codes,
        }
        try:
            mail.send_mail(
                subject_line,
                msg_with_codes if number_of_codes else msg_without_codes,
                from_email_address,
                [cs_email],
                fail_silently=False
            )
            return Response(data, status=HTTP_200_OK)
        except SMTPException:
            error_message = _(
                '[Enterprise API] Failure in sending e-mail to {token_cs_email} for {token_email}'
                ' from {token_enterprise_name}'
            ).format(
                token_cs_email=cs_email,
                token_email=email,
                token_enterprise_name=enterprise_name
            )
            LOGGER.error(error_message)
            return Response(
                {'error': str('Request codes email could not be sent')},
                status=HTTP_500_INTERNAL_SERVER_ERROR
            )
