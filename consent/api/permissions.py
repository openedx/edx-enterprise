# -*- coding: utf-8 -*-
"""
Permission classes for the Consent API.
"""

from rest_framework import permissions

from enterprise.utils import get_request_value


class IsUserInRequest(permissions.BasePermission):
    """
    Permission that checks to see if the request user matches the user indicated in the request body.
    """

    def has_permission(self, request, view):
        return request.user.username == get_request_value(request, 'username', '')


class IsStaffOrUserInRequest(IsUserInRequest):
    """
    Permission that checks to see if the request user is staff or is the user
    indicated in the request body.
    """

    def has_permission(self, request, view):
        if request.user.is_staff:
            return True

        return super(IsStaffOrUserInRequest, self).has_permission(request, view)
