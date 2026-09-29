"""
Pluggable override implementation for the program nudge email's suggested course link.
"""
from typing import Callable
from urllib.parse import urljoin

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser

# Will be replaced with an internal path in ENT-11576.
try:
    from openedx.features.enterprise_support.api import get_enterprise_learner_data_from_db
except ImportError:
    get_enterprise_learner_data_from_db = None


def enterprise_suggested_course_url(
    prev_fn: Callable[..., str],
    user: AbstractBaseUser,
    suggested_course: dict,
    suggested_course_run: dict,
) -> str:
    """
    Return the B2B learner portal landing page for the nudge email's suggested course.

    A learner whose enterprise customer has the learner portal enabled is sent to that
    customer's course landing page on the learner portal instead of the marketing site.
    Every other learner delegates to the platform, which supplies the ordinary
    course-about URL.

    Pluggable override hook point:
    - hook function: `get_suggested_course_url()`
    - platform path: `lms/djangoapps/program_enrollments/management/commands/send_program_course_nudge_email.py`

    Arguments:
        prev_fn: The fallback implementation. Must be used whenever no enterprise learner portal applies.
        user: The user the nudge email is being sent to.
        suggested_course (dict): The catalog course being suggested.
        suggested_course_run (dict): The catalog course run being suggested. Unused here.

    Returns:
        str: the learner portal course landing page fully-qualified URL.
    """
    learner_data = get_enterprise_learner_data_from_db(user)
    enterprise_customer = learner_data[0]['enterprise_customer'] if learner_data else None
    if not (enterprise_customer and enterprise_customer['enable_learner_portal']):
        return prev_fn(
            user=user,
            suggested_course=suggested_course,
            suggested_course_run=suggested_course_run,
        )
    return urljoin(
        settings.ENTERPRISE_LEARNER_PORTAL_BASE_URL,
        '/'.join([enterprise_customer['slug'], 'course', suggested_course['key']]),
    )
