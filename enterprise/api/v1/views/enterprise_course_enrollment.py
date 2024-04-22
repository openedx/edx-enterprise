"""
Views for the ``enterprise-course-enrollment`` API endpoint.
"""
from django_filters.rest_framework import DjangoFilterBackend
from edx_rest_framework_extensions.paginators import DefaultPagination
from rest_framework import filters

from django.core.paginator import Paginator
from django.utils.functional import cached_property

from enterprise import models
from enterprise.api.filters import EnterpriseCourseEnrollmentFilterBackend
from enterprise.api.v1 import serializers
from enterprise.api.v1.views.base_views import EnterpriseReadWriteModelViewSet

try:
    from common.djangoapps.util.query import read_replica_or_default
except ImportError:
    def read_replica_or_default():
        return None


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
