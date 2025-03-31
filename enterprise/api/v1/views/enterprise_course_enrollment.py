"""
Views for the ``enterprise-course-enrollment`` API endpoint.
"""
from django_filters.rest_framework import DjangoFilterBackend
from edx_rest_framework_extensions.paginators import DefaultPagination
from rest_framework import filters, permissions
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.status import HTTP_400_BAD_REQUEST

from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404
from django.utils.functional import cached_property

from enterprise import models
from enterprise.api.filters import EnterpriseCourseEnrollmentFilterBackend
from enterprise.api.utils import CourseRunProgressStatuses  # pylint: disable=cyclic-import
from enterprise.api.v1 import serializers
from enterprise.api.v1.views.base_views import EnterpriseReadWriteModelViewSet

try:
    from common.djangoapps.util.query import read_replica_or_default
except ImportError:
    def read_replica_or_default():
        return None
try:
    from openedx.core.djangoapps.content.course_overviews.api import get_course_overviews
except ImportError:
    get_course_overviews = None


class PaginatorWithOptimizedCount(Paginator):
    """
    Django < 4.2 ORM doesn't strip unused annotations from count queries.

    For example, if we execute this query:

        Book.objects.annotate(Count('chapters')).count()

    it will generate SQL like this:

        SELECT COUNT(*) FROM (SELECT COUNT(...), ... FROM ...) subquery

    This isn't optimal on its own, but it's not a big deal. However, this
    becomes problematic when annotations use subqueries, because it's terribly
    inefficient to execute the subquery for every row in the outer query.

    This class overrides the count() method of Django's Paginator to strip
    unused annotations from the query by requesting only the primary key
    instead of all fields.

    This is a temporary workaround until Django is updated to 4.2, which will
    include a fix for this issue.

    See https://code.djangoproject.com/ticket/32169 for more details.

    TODO: remove this class once Django is updated to 4.2 or higher.
    """
    @cached_property
    def count(self):
        return self.object_list.values("pk").count()


class EnterpriseCourseEnrollmentPagination(DefaultPagination):
    django_paginator_class = PaginatorWithOptimizedCount


class EnterpriseCourseEnrollmentViewSet(EnterpriseReadWriteModelViewSet):
    """
    API views for the ``enterprise-course-enrollment`` API endpoint.
    """

    queryset = models.EnterpriseCourseEnrollment.with_additional_fields.all()
    filter_backends = (filters.OrderingFilter, DjangoFilterBackend, EnterpriseCourseEnrollmentFilterBackend)

    USER_ID_FILTER = 'enterprise_customer_user__user_id'
    FIELDS = (
        'enterprise_customer_user', 'course_id'
    )
    filterset_fields = FIELDS
    ordering_fields = FIELDS

    pagination_class = EnterpriseCourseEnrollmentPagination

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.method == 'GET':
            queryset = queryset.using(read_replica_or_default())
        return queryset

    def get_serializer_class(self):
        """
        Use a special serializer for any requests that aren't read-only.
        """
        if self.request.method in ('GET',):
            return serializers.EnterpriseCourseEnrollmentWithAdditionalFieldsReadOnlySerializer
        return serializers.EnterpriseCourseEnrollmentWriteSerializer


class EnterpriseCourseEnrollmentAdminPagination(PageNumberPagination):
    """
    Custom pagination class for Enterprise Course Enrollment API.
    """
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class EnterpriseCourseEnrollmentAdminViewSet(EnterpriseReadWriteModelViewSet):
    """
    API views for the ``enterprise-course-enrollment-admin`` API endpoint.
    """

    queryset = models.EnterpriseCourseEnrollment.with_additional_fields.all()
    serializer_class = serializers.EnterpriseCourseEnrollmentAdminViewSerializer
    permission_classes = (permissions.IsAuthenticated, permissions.IsAdminUser)
    pagination_class = EnterpriseCourseEnrollmentAdminPagination

    @action(detail=False, methods=['get'])
    def get_enterprise_course_enrollments(self, request):
        """
        Endpoint to get enrollments for a learner by `lms_user_id` and `enterprise_uuid` viewed
        by an admin of that enterprise.

        Parameters:
        - `lms_user_id` (str): Filter results by the LMS user ID.
        - `enterprise_uuid` (str): Filter results by the Enterprise UUID.
        """
        lms_user_id = request.query_params.get('lms_user_id')
        enterprise_uuid = request.query_params.get('enterprise_uuid')
        if not lms_user_id or not enterprise_uuid:
            return Response(
                {"error": "Both 'lms_user_id' and 'enterprise_uuid' are required parameters."},
                status=HTTP_400_BAD_REQUEST
            )
        enterprise_customer_user = get_object_or_404(
            models.EnterpriseCustomerUser,
            user_id=lms_user_id,
            enterprise_customer__uuid=enterprise_uuid
        )
        enterprise_enrollments = models.EnterpriseCourseEnrollment.objects.filter(
            enterprise_customer_user=enterprise_customer_user
        )
        filtered_enterprise_enrollments = [record for record in enterprise_enrollments if record.course_enrollment]
        course_overviews = get_course_overviews([record.course_id for record in filtered_enterprise_enrollments])
        serialized_data = serializers.EnterpriseCourseEnrollmentAdminViewSerializer(
            filtered_enterprise_enrollments,
            many=True,
            context={
                'request': request,
                'enterprise_customer_user': enterprise_customer_user,
                'course_overviews': course_overviews,
            }
        ).data
        page = self.paginate_queryset(serialized_data)
        grouped_data = self._group_course_enrollments_by_status(page)
        return self.get_paginated_response(grouped_data)

    def _group_course_enrollments_by_status(self, course_enrollments):
        """
        Groups course enrollments by their status.

        Args:
            enrollments (list): List of course enrollment dictionaries.

        Returns:
            dict: A dictionary where keys are status names and values are lists of enrollments with that status.
        """
        statuses = {
            CourseRunProgressStatuses.IN_PROGRESS: [],
            CourseRunProgressStatuses.UPCOMING: [],
            CourseRunProgressStatuses.COMPLETED: [],
            CourseRunProgressStatuses.SAVED_FOR_LATER: [],
        }
        for enrollment in course_enrollments:
            status = enrollment.get('course_run_status')
            if status in statuses:
                statuses[status].append(enrollment)
        return statuses
