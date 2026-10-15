"""
Pluggable override implementation for the course home progress view.
"""
# Will be replaced with an internal path in ENT-11576.
try:
    from openedx.features.enterprise_support.utils import get_enterprise_learner_generic_name
except ImportError:
    get_enterprise_learner_generic_name = None


def enterprise_obfuscated_username(
    prev_fn,  # pylint: disable=unused-argument
    request,
    student,  # pylint: disable=unused-argument
):
    """
    Return an enterprise-specific generic name for the student, or None.

    When an enterprise SSO learner has a configured generic name, that name is returned
    so the learner's real username is not exposed in the progress tab.

    Pluggable override hook point:
    - hook function: `obfuscated_username()`
    - platform path: `lms/djangoapps/course_home_api/progress/views.py`

    Arguments:
        prev_fn: the previous (default) implementation. Unused; retained for
            pluggable-override signature compatibility.
        request: the current HTTP request.
        student: the Django User object for the student being viewed.

    Returns:
        str or None: the generic enterprise name, or None if the learner is not an
        enterprise SSO user with a configured generic name.
    """
    return get_enterprise_learner_generic_name(request) or None
