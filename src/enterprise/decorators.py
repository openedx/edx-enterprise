"""
Decorators for enterprise app.
"""

import inspect
import warnings
from functools import wraps
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from requests.utils import quote

from django.http import Http404
from django.shortcuts import redirect

from enterprise.utils import get_enterprise_customer_or_404, get_identity_provider

FRESH_LOGIN_PARAMETER = 'new_enterprise_login'


def deprecated(extra):
    """
    Flag a method as deprecated.

    :param extra: Extra text you'd like to display after the default text.
    """
    def decorator(func):
        """
        Return a decorated function that emits a deprecation warning on use.
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            """
            Wrap the function.
            """
            message = 'You called the deprecated function `{function}`. {extra}'.format(
                function=func.__name__,
                extra=extra
            )
            frame = inspect.currentframe().f_back
            warnings.warn_explicit(
                message,
                category=DeprecationWarning,
                filename=inspect.getfile(frame.f_code),
                lineno=frame.f_lineno
            )
            return func(*args, **kwargs)
        return wrapper
    return decorator


def ignore_warning(warning):
    """
    Ignore any emitted warnings from a function.

    :param warning: The category of warning to ignore.
    """
    def decorator(func):
        """
        Return a decorated function whose emitted warnings are ignored.
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            """
            Wrap the function.
            """
            warnings.simplefilter('ignore', warning)
            return func(*args, **kwargs)
        return wrapper
    return decorator


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
        query_params = request.GET
        tpa_hint_param = query_params.get('tpa_hint')

        # Now verify if the user is logged in. If user is not logged in then
        # send the user to the login screen to sign in with an
        # Enterprise-linked IdP and the pipeline will get them back here.
        if not request.user.is_authenticated:
            parsed_current_url = urlparse(request.get_full_path())
            parsed_query_string = parse_qs(parsed_current_url.query)
            tpa_hint = enterprise_customer.get_tpa_hint(tpa_hint_param)
            if tpa_hint:
                parsed_query_string.update({
                    'tpa_hint': tpa_hint,
                })
            parsed_query_string.update({
                FRESH_LOGIN_PARAMETER: 'yes'
            })
            next_url = '{current_path}?{query_string}'.format(
                current_path=quote(parsed_current_url.path),
                query_string=urlencode(parsed_query_string, doseq=True)
            )
            return redirect(
                '{login_url}?{params}'.format(
                    login_url='/login',
                    params=urlencode(
                        {'next': next_url}
                    )
                )
            )

        # Otherwise, they can proceed to the original view.
        return view(request, *args, **kwargs)

    return wrapper


def force_fresh_session(view):
    """
    View decorator which terminates stale TPA sessions.

    This decorator forces the user to obtain a new session
    the first time they access the decorated view. This prevents
    TPA-authenticated users from hijacking the session of another
    user who may have been previously logged in using the same
    browser window.

    This decorator should be used in conjunction with the
    enterprise_login_required decorator.

    Usage::

        @enterprise_login_required
        @force_fresh_session()
        def my_view(request, enterprise_uuid):
            # Some functionality ...

        OR

        class MyView(View):
            ...
            @method_decorator(enterprise_login_required)
            @method_decorator(force_fresh_session)
            def get(self, request, enterprise_uuid):
                # Some functionality ...
    """
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        """
        Wrap the function.
        """
        if not request.GET.get(FRESH_LOGIN_PARAMETER):
            # The enterprise_login_required decorator promises to set the fresh login URL
            # parameter for this URL when it was the agent that initiated the login process;
            # if that parameter isn't set, we can safely assume that the session is "stale";
            # that isn't necessarily an issue, though. Redirect the user to
            # log out and then come back here - the enterprise_login_required decorator will
            # then take effect prior to us arriving back here again.
            enterprise_customer = get_enterprise_customer_or_404(kwargs.get('enterprise_uuid'))
            if not enterprise_customer.has_multiple_idps:
                provider_id = enterprise_customer.identity_provider \
                    if enterprise_customer.identity_provider else ''
            else:
                provider_id = ''
            sso_provider = get_identity_provider(provider_id)
            if sso_provider:
                # Parse the current request full path, quote just the path portion,
                # then reconstruct the full path string.
                # The path and query portions should be the only non-empty strings here.
                scheme, netloc, path, params, query, fragment = urlparse(request.get_full_path())
                redirect_url = urlunparse((scheme, netloc, quote(path), params, query, fragment))

                return redirect(
                    '{logout_url}?{params}'.format(
                        logout_url='/logout',
                        params=urlencode(
                            {'redirect_url': redirect_url}
                        )
                    )
                )
        return view(request, *args, **kwargs)

    return wrapper


def null_decorator(func):
    """
    Use this decorator to stub out decorators for testing.

    If we're unable to import social_core.pipeline.partial, which is the case in our CI platform,
    we need to be able to wrap the function with something.
    """
    return func
