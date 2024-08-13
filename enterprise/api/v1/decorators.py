"""
Decorators for Enterprise API views.
"""

from functools import wraps

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


def has_any_permissions(*permissions, fn=None):
    """
    Decorator that allows access if the user has at least one of the specified permissions,
    and optionally checks object-level permissions if a `fn` is provided to get the object.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            user = request.user
            pk = fn(request, **kwargs) if fn else kwargs.get('pk')
            LOGGER.info(
                f"[User_Permissions_Check] Checking permissions for user {user.username}, "
                f"permission: {permissions}, "
                f"pk: {pk}"
            )
            has_permission = any(user.has_perm(perm, pk) for perm in permissions)
            LOGGER.info(f"[User_Permissions_Check] User {user.username} has permission: {has_permission}")
            if has_permission:
                return view_func(request, *args, **kwargs)
            LOGGER.error(
                f"[User_Permissions_Check] Access denied for user {user.username} to {view_func.__name__}. "
                f"Method: {request.method}, "
                f"URL: {request.get_full_path()}"
            )
            raise PermissionDenied(
                "Access denied: Only admins and provisioning admins are allowed to access this endpoint.")
        return _wrapped_view
    return decorator
