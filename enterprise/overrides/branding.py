"""
Pluggable override implementations for the platform's branding API.
"""
from typing import Callable, Optional, TypedDict

from crum import get_current_request

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser

# Will be replaced with an internal path in ENT-11576.
try:
    from openedx.features.enterprise_support.utils import (
        get_enterprise_learner_generic_name,
        get_enterprise_learner_portal,
    )
except ImportError:
    get_enterprise_learner_generic_name = None
    get_enterprise_learner_portal = None


class EnterpriseLearnerPortalLink(TypedDict):
    """
    Required keys for the header's enterprise learner portal link.

    Mirrors ``lms.djangoapps.branding.api.EnterpriseLearnerPortalLink``.
    """
    url: str
    logo: str
    name: str


def enterprise_learner_generic_name(prev_fn: Callable[..., str], user: AbstractBaseUser) -> str:
    """
    Return the generic name configured by the learner's enterprise customer.

    An enterprise customer with ``replace_sensitive_sso_username`` enabled hides its SSO
    learners' real usernames behind a generic name. Every other learner -- and every page
    where no generic name applies, such as 404 pages -- delegates to the platform, which
    displays the learner's own username.

    The hook takes no request: the current one comes from crum, which is populated by
    ``CurrentRequestUserMiddleware`` during a request cycle only. Outside one -- a
    management command, a celery task, a shell -- it is None, and this delegates rather
    than calling the platform helper with nothing.

    Pluggable override hook point:
    - hook function: `get_learner_generic_name()`
    - platform path: `lms/djangoapps/branding/api.py`

    Arguments:
        prev_fn: the previous (default) implementation. Must be called, and its result
            returned, whenever no enterprise generic name applies -- the platform's
            callers render this result directly, with no fallback of their own.
        user: the Django User object whose name is being displayed. Not necessarily the
            user making the request: the progress page displays the student being viewed,
            and the user dropdowns display the real user behind a masquerade.

    Returns:
        str: the enterprise generic name, or whatever the previous implementation returns.
    """
    request = get_current_request()
    if request is None:
        return prev_fn(user=user)
    generic_name = get_enterprise_learner_generic_name(request)
    if generic_name:
        return generic_name
    return prev_fn(user=user)


def enterprise_learner_portal_link(
    prev_fn: Callable[..., Optional[EnterpriseLearnerPortalLink]],
) -> Optional[EnterpriseLearnerPortalLink]:
    """
    Return a link to the learner portal of the current viewer's enterprise customer.

    Learners of a customer with the learner portal enabled see the portal's logo in place
    of the site logo, and reach the portal from the header's dashboard link. Every other
    learner, including anonymous visitors, delegates to the platform, which supplies no
    portal.

    The hook takes no arguments at all: it is about the current viewer, so crum supplies
    everything. crum is populated by ``CurrentRequestUserMiddleware`` during a request
    cycle only; outside one it is None, and this delegates rather than calling the
    platform helper with nothing.

    Pluggable override hook point:
    - hook function: `get_enterprise_learner_portal_link()`
    - platform path: `lms/djangoapps/branding/api.py`

    Arguments:
        prev_fn: the previous (default) implementation. Must be called, and its result
            returned, whenever the viewer has no portal-enabled customer.

    Returns:
        dict or None: the portal's absolute URL, logo and name, or whatever the previous
        implementation returns.
    """
    request = get_current_request()
    if request is None:
        return prev_fn()
    portal = get_enterprise_learner_portal(request)
    if not portal:
        return prev_fn()
    return {
        'url': '{base_url}/{slug}'.format(
            base_url=settings.ENTERPRISE_LEARNER_PORTAL_BASE_URL,
            slug=portal.get('slug'),
        ),
        'logo': portal.get('logo'),
        'name': portal.get('name'),
    }
