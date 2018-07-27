# -*- coding: utf-8 -*-

""" Custom API permissions. """

from __future__ import absolute_import, unicode_literals

from rest_framework import permissions


class IsAdminUserOrInGroup(permissions.IsAdminUser):
    """
    Find the requesting user is either staff or belong to specific group.
    It will return a 403 forbidden response with a message if the user is not authorized to access the view.
    """
    ALLOWED_API_GROUPS = []  # pylint: disable=invalid-name
    message = u'User is not allowed to access the view.'

    def has_permission(self, request, view):
        """
        Returns True if the requesting user is either 'staff' or belong to specific group, False otherwise.
        It will also check for group membership against a list of groups in the permissions query parameter.
        """
        return (
            super(IsAdminUserOrInGroup, self).has_permission(request, view) or
            request.user.groups.filter(name__in=self.ALLOWED_API_GROUPS).exists() or
            request.user.groups.filter(name__in=request.query_params.getlist('permissions')).exists()
        )


class HasEnterpriseEnrollmentAPIAccess(IsAdminUserOrInGroup):
    """
    Find the requesting user is either staff or belong to enterprise_enrollment_api_access group.
    It will return a 403 forbidden response with a message if the user is not authorized to access the view.
    """
    def __init__(self):
        """ Initialize the class with a API_ALLOWED_GROUPS """
        self.ALLOWED_API_GROUPS = [u'enterprise_enrollment_api_access', ]  # pylint: disable=invalid-name


class HasEnterpriseDataAPIAccess(IsAdminUserOrInGroup):
    """
    Find the requesting user is either staff or belong to enterprise_data_api_access group.
    It will return a 403 forbidden response with a message if the user is not authorized to access the view.
    """
    def __init__(self):
        """ Initialize the class with a API_ALLOWED_GROUPS """
        self.ALLOWED_API_GROUPS = [u'enterprise_data_api_access', ]  # pylint: disable=invalid-name
