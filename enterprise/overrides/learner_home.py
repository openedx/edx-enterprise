"""
Pluggable override for the learner home enterprise customer lookup.
"""
import logging

# Will be replaced with an internal path in epic 17.
try:
    from openedx.features.enterprise_support.api import (
        enterprise_customer_from_session_or_learner_data,
        get_enterprise_learner_data_from_db,
    )
except ImportError:
    enterprise_customer_from_session_or_learner_data = None
    get_enterprise_learner_data_from_db = None

log = logging.getLogger(__name__)


def enterprise_get_enterprise_customer(prev_fn, user, request, is_masquerading):
    """
    Return the enterprise customer dict for the given user, or None.

    This function overrides the default ``get_enterprise_customer`` implementation in
    ``lms/djangoapps/learner_home/views.py`` via the pluggable override mechanism.

    Arguments:
        prev_fn: the previous (default) implementation, called when the enterprise
            utility is unavailable.
        user: the Django User object.
        request: the current HTTP request.
        is_masquerading (bool): True when the request is a staff masquerade.

    Returns:
        dict or None: enterprise customer data dict, or None if the user is not an
        enterprise customer user.
    """
    if enterprise_customer_from_session_or_learner_data is None:
        return prev_fn(user, request, is_masquerading)

    if is_masquerading:
        learner_data = get_enterprise_learner_data_from_db(user)
        return learner_data[0]['enterprise_customer'] if learner_data else None
    return enterprise_customer_from_session_or_learner_data(request)
