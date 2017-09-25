# -*- coding: utf-8 -*-
"""
Decorators for Enterprise API views.
"""
from __future__ import absolute_import, unicode_literals

from functools import wraps

from rest_framework.exceptions import PermissionDenied, ValidationError

from enterprise.utils import get_enterprise_customer_for_user


def enterprise_customer_required(view):
    """
    Ensure the user making the API request is associated with an EnterpriseCustomer.

    This decorator attempts to find an EnterpriseCustomer associated with the requesting
    user and passes that EnterpriseCustomer to the view as a parameter. It will return a
    PermissionDenied error if an EnterpriseCustomer cannot be found.

    Usage::
        @enterprise_customer_required()
        def my_view(request, enterprise_customer):
            # Some functionality ...

        OR

        class MyView(View):
            ...
            @method_decorator(enterprise_customer_required)
            def get(self, request, enterprise_customer):
                # Some functionality ...
    """
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        """
        Checks for an enterprise customer associated with the user, calls the view function
        if one exists, raises PermissionDenied if not.
        """
        user = request.user
        enterprise_customer = get_enterprise_customer_for_user(user)
        if enterprise_customer:
            args = args + (enterprise_customer,)
            return view(request, *args, **kwargs)
        else:
            raise PermissionDenied(
                'User {username} is not associated with an EnterpriseCustomer.'.format(
                    username=user.username
                )
            )
    return wrapper


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
