"""
Decorators for Enterprise API views.
"""

from functools import wraps

import crum
from rest_framework.exceptions import PermissionDenied, ValidationError

from enterprise.logging import getEnterpriseLogger

LOGGER = getEnterpriseLogger(__name__)


def require_at_least_one_query_parameter(*query_parameter_names):
    """
    Ensure at least one of the specified query parameters are included in the request.

    This decorator checks for the existence of at least one of the specified query
    parameters and passes the values as function parameters to the decorated view.
    If none of the specified query parameters are included in the request, a
    ValidationError is raised.

    Usage::

        @require_at_least_one_query_parameter('program_uuids', 'course_run_ids')
        def my_view(request, program_uuids, course_run_ids):
            # Some functionality ...
    """
    def outer_wrapper(view):
        """ Allow the passing of parameters to require_at_least_one_query_parameter. """
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            """
            Checks for the existence of the specified query parameters, raises a
            ValidationError if none of them were included in the request.
            """
            requirement_satisfied = False
            for query_parameter_name in query_parameter_names:
                query_parameter_values = request.query_params.getlist(query_parameter_name)
                kwargs[query_parameter_name] = query_parameter_values
                if query_parameter_values:
                    requirement_satisfied = True
            if not requirement_satisfied:
                raise ValidationError(
                    detail='You must provide at least one of the following query parameters: {params}.'.format(
                        params=', '.join(query_parameter_names)
                    )
                )
            return view(request, *args, **kwargs)
        return wrapper
    return outer_wrapper


def has_any_permissions(*permissions, **decorator_kwargs):
    """
    Decorator that allows access if the user has at least one of the specified permissions,
    and optionally checks object-level permissions if a `fn` is provided to get the object.

    :param permissions: Permissions added via django_rules add_perm
    :param decorator_kwargs: Arguments for permission checks
    :return: decorator
    """
    def decorator(view):
        """Verify permissions decorator."""
        @wraps(view)
        def wrapped_view(self, request, *args, **kwargs):
            """Wrap for the view function."""
            user = request.user
            fn = decorator_kwargs.get('fn', None)
            if callable(fn):
                obj = fn(request, *args, **kwargs)
            else:
                obj = fn

            crum.set_current_request(request)

            has_permission = [perm for perm in permissions
                              if request.user.has_perm(perm, obj)]
            LOGGER.info(f"[User_Permissions_Check] User {user.username} has permission: {has_permission}")
            if any(has_permission):
                return view(self, request, *args, **kwargs)
            LOGGER.error(
                f"[User_Permissions_Check] Access denied for user {user.username}."
                f"Method: {request.method}, "
                f"URL: {request.get_full_path()}"
            )
            raise PermissionDenied(
                "Access denied: Only admins and provisioning admins are allowed to access this endpoint.")
        return wrapped_view
    return decorator
