"""
Permission classes for the Enterprise API.
"""
from __future__ import absolute_import, unicode_literals

from rest_framework import permissions

from enterprise.api.utils import get_service_usernames


class IsServiceUserOrReadOnly(permissions.IsAuthenticated):
    """
    This request is authenticated as a service user, or is a read-only request.
    """

    def has_permission(self, request, view):
        """
        Enforce that the user is authenticated. If the request isn't read-only (unsafe), then deny permission unless
        the user is a service user.
        """
        service_users = get_service_usernames()

        return (
            request.method in permissions.SAFE_METHODS or
            request.user.username in service_users
        )
