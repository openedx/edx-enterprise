"""
Permission classes for the Enterprise API.
"""
from __future__ import absolute_import, unicode_literals

from logging import getLogger

from rest_framework import permissions

from enterprise import models
from enterprise.api.utils import get_service_usernames
from enterprise.utils import get_enterprise_customer_for_user

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


class IsStaffUserOrLinkedToCommonEnterprise(permissions.IsAuthenticated):
    """
    This request is authenticated as a staff user, or is linked to the endpoint's appointed common Enterprise.
    """

    message = "User must be a staff user or associated with the endpoint's appointed common Enterprise Customer."

    def has_permission(self, request, view):
        """
        Enforce that the user is authenticated. If the user isn't a staff user, or isn't linked to some common
        Enterprise Customer as an Enterprise Customer user, deny the request.

        Expects that the view has a ``cross_check_model`` member which serves as the cross-check model for the existence
        of a common Enterprise Customer.

        Example:
            The Enterprise Catalog view requires a cross-check between the request user (via EnterpriseCustomerUser)
            and an instance of EnterpriseCustomerCatalog -- both must belong to the same enterprise.
        """
        cross_check_enterprise = get_enterprise_customer_for_user(request.user)
        cross_check_model = getattr(view, 'cross_check_model', None)
        belongs_to_common_enterprise = cross_check_model.objects.filter(
            enterprise_customer=cross_check_enterprise
        ).exists()
        if not (request.user.is_staff or belongs_to_common_enterprise):
            error_message = (
                "User '{username}' is not a staff user, and is not associated with "
                "the view's designated common Enterprise Customer from endpoint '{path}'.".format(
                    username=request.user.username,
                    path=request.get_full_path()
                )
            )
            logger.error(error_message)
            return False

        return True
