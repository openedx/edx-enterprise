# -*- coding: utf-8 -*-
"""
Permission classes for the Enterprise API.
"""
from __future__ import absolute_import, unicode_literals

from logging import getLogger

from rest_framework import permissions

from enterprise import models
from enterprise.api.utils import get_service_usernames

logger = getLogger(__name__)  # pylint: disable=invalid-name


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


class IsStaffUserOrLinkedToEnterprise(permissions.IsAuthenticated):
    """
    This request is authenticated as a staff user, or as a user who is linked to the Enterprise Customer.
    """

    message = 'User must be a staff user or associated with the specified Enterprise.'

    def has_object_permission(self, request, view, obj):
        """
        Enforce that the user is authenticated. If the user isn't a staff user, or isn't linked to the
        Enterprise Customer as an Enterprise Customer user, deny the request.
        The obj argument is expected to be an Enterprise Customer.
        """
        if not request.user.is_staff and not models.EnterpriseCustomerUser.objects.filter(
                enterprise_customer=obj,
                user_id=request.user.id,
        ).exists():
            error_message = (
                "User '{username}' is not a staff user, and is not associated with "
                "Enterprise {enterprise_name} from endpoint '{path}'.".format(
                    username=request.user.username,
                    enterprise_name=obj.name,
                    path=request.get_full_path()
                )
            )
            logger.error(error_message)
            return False
        return True
