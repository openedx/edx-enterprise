# -*- coding: utf-8 -*-
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


class IsStaffOrLinkedToEnterpriseCustomerFilterBackend(filters.BaseFilterBackend):
    """
    Filter based on the requesting user's status as staff or linkage to a related EnterpriseCustomer.

    Using this backend will ensure that results returned are owned by an EnterpriseCustomer which
    the requesting user is linked to.
    """

    def filter_queryset(self, request, queryset, view):
        """ Filter the queryset. """
        user = request.user
        if not user.is_staff:
            return queryset.filter(
                enterprise_customer__enterprise_customer_users__user_id=user.id
            )
        return queryset
