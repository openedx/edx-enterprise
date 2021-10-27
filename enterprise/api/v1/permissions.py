""" Custom API permissions. """

from rest_framework import permissions


class IsInEnterpriseGroup(permissions.BasePermission):
    """
    Find out if the requesting user belongs to a django group meant for granting access to an enterprise feature.
    This check applies to both staff and non-staff users.
    """
    ALLOWED_API_GROUPS = []
    message = 'User is not allowed to access the view.'

    def has_permission(self, request, view):
        return (
            super().has_permission(request, view) and (
                request.user.groups.filter(name__in=self.ALLOWED_API_GROUPS).exists() or
                request.user.groups.filter(name__in=request.query_params.getlist('permissions')).exists()
            )
        )
