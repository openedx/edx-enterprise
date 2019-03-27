# -*- coding: utf-8 -*-

""" Custom API permissions. """

from __future__ import absolute_import, unicode_literals

import waffle
from rest_framework import permissions

from enterprise.constants import ENTERPRISE_ROLE_BASED_ACCESS_CONTROL_SWITCH


class IsInEnterpriseGroup(permissions.BasePermission):
    """
    Find out if the requesting user belongs to a django group meant for granting access to an enterprise feature.
    This check applies to both staff and non-staff users.
    """
    ALLOWED_API_GROUPS = []  # pylint: disable=invalid-name
    message = u'User is not allowed to access the view.'

    def has_permission(self, request, view):
        if waffle.switch_is_active(ENTERPRISE_ROLE_BASED_ACCESS_CONTROL_SWITCH):
            return True

        return (
            super(IsInEnterpriseGroup, self).has_permission(request, view) and (
                request.user.groups.filter(name__in=self.ALLOWED_API_GROUPS).exists() or
                request.user.groups.filter(name__in=request.query_params.getlist('permissions')).exists()
            )
        )


class IsAdminUserOrInGroup(permissions.IsAdminUser):
    """
    Find out if the requesting user is either staff or belongs to specific django group.
    It will return a 403 forbidden response with a message if the user is not authorized to access the view.
    """
    ALLOWED_API_GROUPS = []  # pylint: disable=invalid-name
    message = u'User is not allowed to access the view.'

    def has_permission(self, request, view):
        """
        Returns True if the requesting user is either 'staff' or belong to specific group, False otherwise.
        It will also check for group membership against a list of groups in the permissions query parameter.
        """
        if waffle.switch_is_active(ENTERPRISE_ROLE_BASED_ACCESS_CONTROL_SWITCH):
            return True

        return (
            super(IsAdminUserOrInGroup, self).has_permission(request, view) or
            request.user.groups.filter(name__in=self.ALLOWED_API_GROUPS).exists() or
            request.user.groups.filter(name__in=request.query_params.getlist('permissions')).exists()
        )


class HasEnterpriseEnrollmentAPIAccess(IsAdminUserOrInGroup):
    """
    Find the requesting user has access to the Enterprise Enrollment API feature set.
    """
    def __init__(self):
        """ Initialize the class with a API_ALLOWED_GROUPS """
        self.ALLOWED_API_GROUPS = [u'enterprise_enrollment_api_access', ]  # pylint: disable=invalid-name


class HasEnterpriseDataAPIAccess(IsInEnterpriseGroup):
    """
    Find the requesting user has access to the Enterprise Data API feature set.
    """
    def __init__(self):
        """ Initialize the class with a API_ALLOWED_GROUPS """
        self.ALLOWED_API_GROUPS = [u'enterprise_data_api_access', ]  # pylint: disable=invalid-name
