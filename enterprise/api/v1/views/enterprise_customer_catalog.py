"""
Write views for the ``enterprise-customer-catalog`` API endpoint.
"""
from urllib.parse import quote_plus, unquote

from edx_rbac.decorators import permission_required
from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework_xml.renderers import XMLRenderer

from django.conf import settings
from django.http import Http404
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _

from enterprise import models
from enterprise.api.utils import get_enterprise_customer_from_catalog_id
from enterprise.api.v1 import serializers
from enterprise.api.v1.decorators import require_at_least_one_query_parameter
from enterprise.api.v1.views.base_views import EnterpriseReadOnlyModelViewSet, EnterpriseWriteOnlyModelViewSet
from enterprise.constants import COURSE_KEY_URL_PATTERN
from enterprise.logging import getEnterpriseLogger

LOGGER = getEnterpriseLogger(__name__)


class EnterpriseCustomerCatalogWriteViewSet(EnterpriseWriteOnlyModelViewSet):
    """
    API write only views for the ``enterprise-customer-catalog`` API endpoint.
    """
    queryset = models.EnterpriseCustomerCatalog.objects.all()
    permission_classes = (permissions.IsAdminUser,)
    serializer_class = serializers.EnterpriseCustomerCatalogWriteOnlySerializer

    def create(self, request, *args, **kwargs):
        """
        Creates a new EnterpriseCustomerCatalog and returns the created object.

        If an EnterpriseCustomerCatalog already exists for the given enterprise_customer and enterprise_catalog_query,
        returns the existing object.

        URL: /enterprise/api/v1/enterprise-customer-catalog/

        Method: POST

        Payload::

          {
            "title":  string - Title of the catalog,
            "enterprise_customer": string - UUID of an existing enterprise customer,
            "enterprise_catalog_query": string - id of an existing enterprise catalog query,
          }

        Returns 201 if a new EnterpriseCustomerCatalog was created, 200 if an existing EnterpriseCustomerCatalog was
        """

        enterprise_customer_uuid = request.data.get('enterprise_customer')
        enterprise_catalog_query_id = request.data.get('enterprise_catalog_query')
        enterprise_customer_catalog_list = models.EnterpriseCustomerCatalog.objects.filter(
            enterprise_customer=enterprise_customer_uuid)
        for catalog in enterprise_customer_catalog_list:
            catalog_query = catalog.enterprise_catalog_query
            if catalog_query is not None and catalog_query.id == int(enterprise_catalog_query_id):
                serialized_customer_catalog = serializers.EnterpriseCustomerCatalogWriteOnlySerializer(
                    catalog)
                LOGGER.info(
                    'EnterpriseCustomerCatalog already exists for enterprise_customer_uuid: %s '
                    'and enterprise_catalog_query_id: %s, using existing catalog: %s',
                    enterprise_customer_uuid, enterprise_catalog_query_id, catalog.uuid)
                return Response(serialized_customer_catalog.data, status=status.HTTP_200_OK)
        LOGGER.info(
            'Creating new EnterpriseCustomerCatalog for enterprise_customer_uuid: %s '
            'and enterprise_catalog_query_id: %s',
            enterprise_customer_uuid, enterprise_catalog_query_id)
        return super().create(request, *args, **kwargs)


class EnterpriseCustomerCatalogViewSet(EnterpriseReadOnlyModelViewSet):
    """
    API Views for performing search through course discovery at the ``enterprise_catalogs`` API endpoint.
    """
    queryset = models.EnterpriseCustomerCatalog.objects.all()

    USER_ID_FILTER = 'enterprise_customer__enterprise_customer_users__user_id'
    FIELDS = (
        'uuid', 'enterprise_customer',
    )
    filterset_fields = FIELDS
    ordering_fields = FIELDS
    renderer_classes = (JSONRenderer, XMLRenderer,)

    @permission_required('enterprise.can_view_catalog', fn=lambda request, *args, **kwargs: None)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @permission_required(
        'enterprise.can_view_catalog',
        fn=lambda request, *args, **kwargs: get_enterprise_customer_from_catalog_id(kwargs['pk']))
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def get_serializer_class(self):
        view_action = getattr(self, 'action', None)
        if view_action == 'retrieve':
            return serializers.EnterpriseCustomerCatalogDetailSerializer
        return serializers.EnterpriseCustomerCatalogSerializer

    @method_decorator(require_at_least_one_query_parameter('course_run_ids', 'program_uuids'))
    @action(detail=True)
    # pylint: disable=unused-argument
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

    @action(detail=True, url_path='courses/{}'.format(COURSE_KEY_URL_PATTERN))
    @permission_required(
        'enterprise.can_view_catalog',
        fn=lambda request, pk, course_key: get_enterprise_customer_from_catalog_id(pk))
    def course_detail(self, request, pk, course_key):  # pylint: disable=unused-argument
        """
        Return the metadata for the specified course.

        The course needs to be included in the specified EnterpriseCustomerCatalog
        in order for metadata to be returned from this endpoint.
        """
        enterprise_customer_catalog = self.get_object()
        course = enterprise_customer_catalog.get_course(course_key)
        if not course:
            error_message = _(
                '[Enterprise API] CourseKey not found in the Catalog. Course: {course_key}, Catalog: {catalog_id}'
            ).format(
                course_key=course_key,
                catalog_id=enterprise_customer_catalog.uuid,
            )
            LOGGER.warning(error_message)
            raise Http404

        context = self.get_serializer_context()
        context['enterprise_customer_catalog'] = enterprise_customer_catalog
        serializer = serializers.CourseDetailSerializer(course, context=context)
        return Response(serializer.data)

    @action(detail=True, url_path='course_runs/{}'.format(settings.COURSE_ID_PATTERN))
    @permission_required(
        'enterprise.can_view_catalog',
        fn=lambda request, pk, course_id: get_enterprise_customer_from_catalog_id(pk))
    def course_run_detail(self, request, pk, course_id):  # pylint: disable=unused-argument
        """
        Return the metadata for the specified course run.

        The course run needs to be included in the specified EnterpriseCustomerCatalog
        in order for metadata to be returned from this endpoint.
        """
        enterprise_customer_catalog = self.get_object()
        course_run = enterprise_customer_catalog.get_course_run(course_id)
        if not course_run:
            error_message = _(
                '[Enterprise API] CourseRun not found in the Catalog. CourseRun: {course_id}, Catalog: {catalog_id}'
            ).format(
                course_id=course_id,
                catalog_id=enterprise_customer_catalog.uuid,
            )
            LOGGER.warning(error_message)
            raise Http404

        context = self.get_serializer_context()
        context['enterprise_customer_catalog'] = enterprise_customer_catalog
        serializer = serializers.CourseRunDetailSerializer(course_run, context=context)
        return Response(serializer.data)

    @action(detail=True, url_path='programs/(?P<program_uuid>[^/]+)')
    @permission_required(
        'enterprise.can_view_catalog',
        fn=lambda request, pk, program_uuid: get_enterprise_customer_from_catalog_id(pk))
    def program_detail(self, request, pk, program_uuid):  # pylint: disable=unused-argument
        """
        Return the metadata for the specified program.

        The program needs to be included in the specified EnterpriseCustomerCatalog
        in order for metadata to be returned from this endpoint.
        """
        enterprise_customer_catalog = self.get_object()
        program = enterprise_customer_catalog.get_program(program_uuid)
        if not program:
            error_message = _(
                '[Enterprise API] Program not found in the Catalog. Program: {program_uuid}, Catalog: {catalog_id}'
            ).format(
                program_uuid=program_uuid,
                catalog_id=enterprise_customer_catalog.uuid,
            )
            LOGGER.warning(error_message)
            raise Http404

        context = self.get_serializer_context()
        context['enterprise_customer_catalog'] = enterprise_customer_catalog
        serializer = serializers.ProgramDetailSerializer(program, context=context)
        return Response(serializer.data)
