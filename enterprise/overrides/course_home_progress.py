"""
Pluggable override for the course home progress view username obfuscation.
"""
import logging

# Will be replaced with an internal path in ENT-11576.
try:
    from openedx.features.enterprise_support.utils import (  # pylint: disable=import-error
        get_enterprise_learner_generic_name,
    )
except ImportError:
    get_enterprise_learner_generic_name = None

log = logging.getLogger(__name__)


def enterprise_obfuscated_username(
    prev_fn,
    request,
    student,
):
    """
    Return an enterprise-specific generic name for the student, or None.

    This function overrides the default ``obfuscated_username`` implementation in
    ``lms/djangoapps/course_home_api/progress/views.py`` via the pluggable override
    mechanism. When an enterprise SSO learner has a configured generic name, that name
    is returned so the learner's real username is not exposed in the progress tab.

    Arguments:
        prev_fn: the previous (default) implementation, called when the enterprise
            utility is unavailable.
        request: the current HTTP request.
        student: the Django User object for the student being viewed.

    Returns:
        str or None: the generic enterprise name, or None if the learner is not an
        enterprise SSO user with a configured generic name.
    """
    if get_enterprise_learner_generic_name is None:
        return prev_fn(request, student)
    return get_enterprise_learner_generic_name(request) or None
