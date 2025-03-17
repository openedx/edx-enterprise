"""
Views for the ``enterprise-customer-members`` API endpoint.
"""

from collections import OrderedDict

from rest_framework import permissions, response, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from django.core.exceptions import ValidationError
from django.db import connection

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
        query_params = self.request.query_params
        param_serializers = serializers.EnterpriseCustomerMembersRequestQuerySerializer(
            data=query_params
        )
        if not param_serializers.is_valid():
            return Response(param_serializers.errors, status=400)
        enterprise_uuid = kwargs.get("enterprise_uuid", None)
        # Raw sql is picky about uuid format
        uuid_no_dashes = str(enterprise_uuid).replace("-", "")
        users = []
        user_query = param_serializers.validated_data.get('user_query')
        is_reversed = param_serializers.validated_data.get('is_reversed', False)
        sort_by = param_serializers.validated_data.get('sort_by')
        user_id = param_serializers.validated_data.get('user_id')
        # On logistration, the name field of auth_userprofile is populated, but if it's not
        # filled in, we check the auth_user model for it's first/last name fields
        # https://2u-internal.atlassian.net/wiki/spaces/ENGAGE/pages/747143186/Use+of+full+name+in+edX#Data-on-Name-Field
        query = """
            WITH users AS (
                SELECT
                    au.id,
                    au.email,
                    au.date_joined,
                    coalesce(NULLIF(aup.name, ''), au.username) as full_name
                FROM enterprise_enterprisecustomeruser ecu
                INNER JOIN auth_user as au on ecu.user_id = au.id
                LEFT JOIN auth_userprofile as aup on au.id = aup.user_id
                WHERE
                    ecu.enterprise_customer_id = %s
                AND
                    ecu.linked = 1
            ) SELECT * FROM users {user_query_filter} ORDER BY full_name;
        """
        try:
            with connection.cursor() as cursor:
                if user_query:
                    like_user_query = f"%{user_query}%"
                    sql_to_execute = query.format(
                        user_query_filter="WHERE full_name LIKE %s OR email LIKE %s"
                    )
                    cursor.execute(
                        sql_to_execute,
                        [uuid_no_dashes, like_user_query, like_user_query],
                    )
                elif user_id:
                    user_id_query = f"{user_id}"
                    sql_to_execute = query.format(
                        user_query_filter="WHERE id = %s"
                    )
                    cursor.execute(sql_to_execute, [uuid_no_dashes, user_id_query])
                else:
                    sql_to_execute = query.format(user_query_filter="")
                    cursor.execute(sql_to_execute, [uuid_no_dashes])
                users.extend(cursor.fetchall())

        except ValidationError:
            # did not find UUID match in either EnterpriseCustomerUser
            return response.Response(
                {"detail": "Could not find enterprise uuid {}".format(enterprise_uuid)},
                status=status.HTTP_404_NOT_FOUND,
            )

        if sort_by:
            lambda_keys = {
                # 3 and 2 are indices in the tuple associated to a user row (uuid, email, joined_org, name)
                'name': lambda t: t[3],
                'joined_org': lambda t: t[2],
            }
            users = sorted(users, key=lambda_keys.get(sort_by), reverse=is_reversed)

        # paginate the queryset
        users_page = self.paginator.paginate_queryset(users, request, view=self)

        # serialize the paged dataset
        serializer = serializers.EnterpriseMembersSerializer(users_page, many=True)
        return self.paginator.get_paginated_response(serializer.data)
