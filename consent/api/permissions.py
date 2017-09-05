# -*- coding: utf-8 -*-
"""
Permission classes for the Consent API.
"""

from __future__ import absolute_import, unicode_literals

from rest_framework import permissions


class IsUserInRequest(permissions.BasePermission):
    """
    Permission that checks to see if the request user matches the user indicated in the request body.
    """

    def has_permission(self, request, view):
        if request.method == 'GET':
            username_in_request = request.query_params.get('username')
        else:
            username_in_request = request.data.get('username')
        if request.user.username == username_in_request:
            return True


class IsStaffOrUserInRequest(IsUserInRequest):
    """
    Permission that checks to see if the request user is staff or is the user
    indicated in the request body.
    """

    def has_permission(self, request, view):
        if request.user.is_staff:
            return True

        return super(IsStaffOrUserInRequest, self).has_permission(request, view)
