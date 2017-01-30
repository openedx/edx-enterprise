"""
Filters for enterprise API.
"""
from __future__ import absolute_import, unicode_literals

from rest_framework import filters

from django.contrib.auth.models import User


class EnterpriseCustomerUserFilterBackend(filters.BaseFilterBackend):
    """
    Allow filtering based on user's email or username on enterprise customer user api endpoint.
    """
    def filter_queryset(self, request, queryset, view):
        email = request.query_params.get('email', None)
        username = request.query_params.get('username', None)
        query_parameters = {}

        if email:
            query_parameters.update(email=email)
        if username:
            query_parameters.update(username=username)

        # Apply filter only if there are some filter parameters
        if query_parameters:
            users = User.objects.filter(**query_parameters).values_list('id', flat=True)
            queryset = queryset.filter(user_id__in=users)
        return queryset
