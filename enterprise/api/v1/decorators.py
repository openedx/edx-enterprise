# -*- coding: utf-8 -*-
"""
Decorators for Enterprise API views.
"""
from __future__ import absolute_import, unicode_literals

from functools import wraps

from rest_framework.exceptions import PermissionDenied

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
