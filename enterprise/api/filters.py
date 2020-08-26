# -*- coding: utf-8 -*-
"""
Filters for enterprise API.
"""

from rest_framework import filters

from django.contrib.auth.models import User


class UserFilterBackend(filters.BaseFilterBackend):
    """
    Filter backend for any view that needs to filter against the requesting user's ID.

    * Staff users will bypass this filter.
    * Non-staff users will receive only those objects that match their own user ID.

    This requires that `USER_ID_FILTER` be set in the view as a class variable, to identify
    the object's relationship to a user ID.
    """

    def filter_queryset(self, request, queryset, view):
        """
        Filter only for the user's ID if non-staff.
        """
        if not request.user.is_staff:
            filter_kwargs = {view.USER_ID_FILTER: request.user.id}
            queryset = queryset.filter(**filter_kwargs)
        return queryset


class EnterpriseCustomerUserFilterBackend(filters.BaseFilterBackend):
    """
    Allow filtering based on user's email or username on enterprise customer user api endpoint.
    """

    def filter_queryset(self, request, queryset, view):
        """
        Apply incoming filters only if user is staff. If not, only filter by user's ID.
        """
        if request.user.is_staff:
            email = request.query_params.get('email', None)
            username = request.query_params.get('username', None)
            query_parameters = {}

            if email:
                query_parameters.update(email=email)
            if username:
                query_parameters.update(username=username)
            if query_parameters:
                users = User.objects.filter(**query_parameters).values_list('id', flat=True)
                queryset = queryset.filter(user_id__in=users)
        else:
            queryset = queryset.filter(user_id=request.user.id)

        return queryset


class EnterpriseLinkedUserFilterBackend(filters.BaseFilterBackend):
    """
    Filter backend to return user's linked enterprises only

    * Staff users will bypass this filter.
    * Non-staff users will receive only their linked enterprises.
    """

    def filter_queryset(self, request, queryset, view):
        """
        Filter out enterprise customer if learner is not linked
        """
        if not request.user.is_staff:
            filter_kwargs = {
                view.USER_ID_FILTER: request.user.id,
                'enterprise_customer_users__linked': 1
            }
            queryset = queryset.filter(**filter_kwargs)

        return queryset
