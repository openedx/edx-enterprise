"""
Decorators for Enterprise API views.
"""

from functools import wraps

from rest_framework.exceptions import ValidationError, AuthenticationFailed
from rest_framework.status import HTTP_403_FORBIDDEN

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


def has_permission_to_create_enterprise_customer():
    """
    Ensure that user has permission to create enterprise_customers.
    Only provisioning admins or admins with can_access_admin_dashboard should be allowed 
    to create enterprise customers
    """
    def outer_wrapper(view):
        """ Allow the passing of parameters to has_permission_to_create_enterprise_customer. """
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            """
            Checks for the existence of at least one of the permissions and raises
            AuthenticationFailed error if none of them are availalable.
            """
            PROVISIONING_ADMIN_ALLOWED_API_GROUPS = ['provisioning-admins-group']
            if request.user.groups.filter(name__in=PROVISIONING_ADMIN_ALLOWED_API_GROUPS).exists() or\
                request.user.has_perm('enterprise.can_access_admin_dashboard'):
                return view(request, *args, **kwargs)
                    
            raise AuthenticationFailed(
                detail='Access denied: Only admins are allowed to access this endpoint.',
                code=HTTP_403_FORBIDDEN
            )
        return wrapper
    return outer_wrapper
