"""
Views for the ``enterprise-customer-members`` API endpoint.
"""

from collections import OrderedDict

from rest_framework import permissions, response
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from django.apps import apps
from django.db import connection
from django.db import OperationalError

from enterprise import models
from enterprise.api.v1 import serializers
from enterprise.api.v1.views.base_views import EnterpriseReadOnlyModelViewSet
from enterprise.logging import getEnterpriseLogger

LOGGER = getEnterpriseLogger(__name__)


class EnterpriseCustomerMembersPaginator(PageNumberPagination):
    """Custom paginator for the enterprise customer members."""

    page_size = 10
    page_size_query_param = 'page_size'

    def get_paginated_response(self, data):
        """Return a paginated style `Response` object for the given output data."""
        return response.Response(
            OrderedDict(
                [
                    ("count", self.page.paginator.count),
                    ("num_pages", self.page.paginator.num_pages),
                    ("next", self.get_next_link()),
                    ("previous", self.get_previous_link()),
                    ("results", data),
                ]
            )
        )

    def paginate_queryset(self, queryset, request, view=None):
        """
        Paginate a queryset if required, either returning a page object,
        or `None` if pagination is not configured for this view.

        """
        if isinstance(queryset, filter):
            queryset = list(queryset)

        return super().paginate_queryset(queryset, request, view)


class EnterpriseCustomerMembersViewSet(EnterpriseReadOnlyModelViewSet):
    """
    API views for the ``enterprise-customer-members`` API endpoint.
    """
    @staticmethod
    def has_auth_userprofile_table():
        """
        Some minimal / test Open edX environments do not include auth_userprofile.
        Detect its presence explicitly instead of relying on SQL failure.
        """
        try:
            UserProfile = apps.get_model("auth", "UserProfile")
        except LookupError:
            # Model not installed at all
            return False

        return UserProfile._meta.db_table in connection.introspection.table_names()

    QUERY_WITH_PROFILE = """
        WITH users AS (
            SELECT
                au.id,
                au.email,
                au.date_joined,
                coalesce(NULLIF(aup.name, ''), au.username) AS full_name
            FROM enterprise_enterprisecustomeruser ecu
            INNER JOIN auth_user au ON ecu.user_id = au.id
            LEFT JOIN auth_userprofile aup ON au.id = aup.user_id
            INNER JOIN enterprise_systemwideenterpriseuserroleassignment swra
                ON swra.user_id = au.id
            INNER JOIN enterprise_systemwideenterpriserole sr
                ON sr.id = swra.role_id
            WHERE
                ecu.enterprise_customer_id = %s
                AND ecu.linked = 1
                AND ecu.active = 1
                AND sr.name = 'enterprise_learner'
        )
        SELECT * FROM users {user_query_filter}
        ORDER BY full_name;
    """
    QUERY_WITHOUT_PROFILE = """
        WITH users AS (
            SELECT
                au.id,
                au.email,
                au.date_joined,
                au.username AS full_name
            FROM enterprise_enterprisecustomeruser ecu
            INNER JOIN auth_user au ON ecu.user_id = au.id
            INNER JOIN enterprise_systemwideenterpriseuserroleassignment swra
                ON swra.user_id = au.id
            INNER JOIN enterprise_systemwideenterpriserole sr
                ON sr.id = swra.role_id
            WHERE
                ecu.enterprise_customer_id = %s
                AND ecu.linked = 1
                AND ecu.active = 1
                AND sr.name = 'enterprise_learner'
        )
        SELECT * FROM users {user_query_filter}
        ORDER BY full_name;
    """
    queryset = models.EnterpriseCustomerUser.objects.all()
    serializer_class = serializers.EnterpriseMembersSerializer

    permission_classes = (permissions.IsAuthenticated,)
    paginator = EnterpriseCustomerMembersPaginator()

    def get_members(self, request, *args, **kwargs):
        """
        Get all members associated with that enterprise customer

        Request Arguments:
        - ``enterprise_uuid`` (URL location, required): The uuid of the enterprise from which learners should be listed.

        Optional query params:
        - ``user_query`` (string, optional): Filter the returned members by user name and email with a provided
        sub-string
        - ``sort_by`` (string, optional): Specify how the returned members should be ordered. Supported sorting values
        are `joined_org`, `name`, and `enrollments`.
        - ``is_reversed`` (bool, optional): Include to reverse the records in descending order. By default, the results
        returned are in ascending order.
        - ``user_id`` (string, optional): Specify a user_id in order to fetch a single enterprise customer member,
        cannot be passed in conjuction with a user_query
        """
        query_params = request.query_params
        param_serializer = serializers.EnterpriseCustomerMembersRequestQuerySerializer(
            data=query_params
        )
        if not param_serializer.is_valid():
            return Response(param_serializer.errors, status=400)

        enterprise_uuid = kwargs.get("enterprise_uuid")
        uuid_no_dashes = str(enterprise_uuid).replace("-", "")

        user_query = param_serializer.validated_data.get("user_query")
        user_id = param_serializer.validated_data.get("user_id")
        sort_by = param_serializer.validated_data.get("sort_by")
        is_reversed = param_serializer.validated_data.get("is_reversed", False)

        base_query = (
            self.QUERY_WITH_PROFILE
            if self.has_auth_userprofile_table()
            else self.QUERY_WITHOUT_PROFILE
        )

        users = []

        with connection.cursor() as cursor:
            if user_query:
                sql = base_query.format(
                    user_query_filter="WHERE full_name LIKE %s OR email LIKE %s"
                )
                like_query = f"%{user_query}%"
                cursor.execute(
                    sql,
                    [uuid_no_dashes, like_query, like_query],
                )

            elif user_id:
                sql = base_query.format(user_query_filter="WHERE id = %s")
                cursor.execute(
                    sql,
                    [uuid_no_dashes, user_id],
                )

            else:
                sql = base_query.format(user_query_filter="")
                cursor.execute(
                    sql,
                    [uuid_no_dashes],
                )

            users = cursor.fetchall()

        if sort_by:
            sort_key_map = {
                "name": lambda row: row[3],
                "joined_org": lambda row: row[2],
            }
            users = sorted(
                users,
                key=sort_key_map.get(sort_by),
                reverse=is_reversed,
            )

        # paginate the queryset
        users_page = self.paginator.paginate_queryset(users, request, view=self)

        # serialize the paged dataset
        serializer = serializers.EnterpriseMembersSerializer(users_page, many=True)
        return self.paginator.get_paginated_response(serializer.data)
