# -*- coding: utf-8 -*-
"""
Decorators for enterprise app.
"""
from __future__ import absolute_import, unicode_literals

from functools import wraps

from requests.utils import quote

from django.http import Http404
from django.shortcuts import redirect

from enterprise.utils import get_enterprise_customer_or_404, get_identity_provider
from six.moves.urllib.parse import urlencode  # pylint: disable=import-error


def disable_for_loaddata(signal_handler):
    """
    Use this decorator to turn off signal handlers when loading fixture data.

    Django docs instruct to avoid further changes to the DB if raw=True as it might not be in a consistent state.
    See https://docs.djangoproject.com/en/dev/ref/signals/#post-save
    """
    # http://stackoverflow.com/a/15625121/882918
    @wraps(signal_handler)
    def wrapper(*args, **kwargs):
        """
        Wrap the function.
        """
        if kwargs.get('raw', False):
            return
        signal_handler(*args, **kwargs)
    return wrapper


def null_decorator(func):
    """
    Use this decorator to stub out decorators for testing.

    If we're unable to import social_core.pipeline.partial, which is the case in our CI platform,
    we need to be able to wrap the function with something.
    """
    return func


def enterprise_login_required(view):
    """
    View decorator for allowing authenticated user with valid enterprise UUID.

    This decorator requires enterprise identifier as a parameter
    `enterprise_uuid`.

    This decorator will throw 404 if no kwarg `enterprise_uuid` is provided to
    the decorated view .

    If there is no enterprise in database against the kwarg `enterprise_uuid`
    or if the user is not authenticated then it will redirect the user to the
    enterprise-linked SSO login page.

    Usage::
        @enterprise_login_required()
        def my_view(request, enterprise_uuid):
            # Some functionality ...

        OR

        class MyView(View):
            ...
            @method_decorator(enterprise_login_required)
            def get(self, request, enterprise_uuid):
                # Some functionality ...

    """
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        """
        Wrap the decorator.
        """
        if 'enterprise_uuid' not in kwargs:
            raise Http404

        enterprise_uuid = kwargs['enterprise_uuid']
        enterprise_customer = get_enterprise_customer_or_404(enterprise_uuid)
        provider_id = enterprise_customer.identity_provider or ''
        sso_provider = None

        try:
            sso_provider = get_identity_provider(provider_id)
        except ValueError:
            pass

        decorator_already_processed = request.GET.get('session_cleared')

        if not request.user.is_authenticated():
            # If the user isn't logged in, send them to the log in page and redirect them
            # back to the original view, indicating that the decorator has been processed.
            next_url = '{current_url}?{params}'.format(
                current_url=quote(request.get_full_path()),
                params=urlencode(
                    [
                        ('tpa_hint', provider_id),
                        ('session_cleared', 'yes')
                    ]
                )
            )

            return redirect(
                '{login_url}?{params}'.format(
                    login_url='/login',
                    params=urlencode(
                        {'next': next_url}
                    )
                )
            )

        if not decorator_already_processed and sso_provider and sso_provider.drop_existing_session:
            # If the user is logged in, this is their first time hitting the decorator,
            # and the sso provider is configured to drop the session, send them to
            # the logout page with a redirect back to the original view,
            # indicating the decorator has been processed.
            return redirect(
                '{logout_url}?{params}'.format(
                    logout_url='/logout',
                    params=urlencode(
                        {'redirect_url': quote(request.get_full_path())}
                    )
                )
            )

        # Otherwise, they can proceed to the original view.
        return view(request, *args, **kwargs)

    return wrapper
