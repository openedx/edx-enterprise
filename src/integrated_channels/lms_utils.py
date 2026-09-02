"""
A utility collection for calls from integrated_channels to LMS APIs
If integrated_channels calls LMS APIs, put them here for better tracking.
"""
from opaque_keys.edx.keys import CourseKey

try:
    from lms.djangoapps.certificates.api import get_certificate_for_user
    from lms.djangoapps.grades.course_grade_factory import CourseGradeFactory
    from lms.djangoapps.grades.models import PersistentCourseGrade
    from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
except ImportError:
    get_certificate_for_user = None
    CourseGradeFactory = None
    CourseOverview = None
    PersistentCourseGrade = None

try:
    from lms.djangoapps.courseware.courses import get_course_blocks_completion_summary
except ImportError:
    get_course_blocks_completion_summary = None

from enterprise.utils import NotConnectedToOpenEdX


def get_persistent_grade(course_key, user):
    """
    Get the persistent course grade record for this course and user, or None
    """
    try:
        grade = PersistentCourseGrade.read(user.id, course_key)
    except PersistentCourseGrade.DoesNotExist:
        return None
    return grade


def get_course_certificate(course_key, user):
    """
    A course certificate for a user (must be a django.contrib.auth.User instance).
    If there is a problem loading the get_certificate_for_user function, throws NotConnectedToOpenEdX
    If issues with course_key string, throws a InvalidKeyError
    Arguments:
        course_key (string): course key
        user (django.contrib.auth.User): user instance
    Returns a certificate as a dict, for example:
        {
            "username": "bob",
            "course_id": "edX/DemoX/Demo_Course",
            "certificate_type": "verified",
            "created_date": "2015-12-03T13:14:28+0000",
            "status": "downloadable",
            "is_passing": true,
            "download_url": "http://www.example.com/cert.pdf",
            "grade": "0.98"
        }
    """
    if not get_certificate_for_user:
        raise NotConnectedToOpenEdX(
            'To use this function, this package must be '
            'installed in an Open edX environment.'
        )
    course_id = CourseKey.from_string(course_key)
    user_cert = get_certificate_for_user(username=user.username, course_key=course_id)
    return user_cert


def get_single_user_grade(course_key, user):
    """
    Returns a grade for the user (must be a django.contrib.auth.User instance).
    If there is a problem loading the CourseGradeFactory class, throws NotConnectedToOpenEdX
    If issues with course_key string, throws a InvalidKeyError
    Args:
        course_key (string): string course key
        user (django.contrib.auth.User): user instance

    Returns:
        A CourseGrade object with at least these fields:
            - percent (Number)
            - passed (Boolean)
    """
    if not CourseGradeFactory:
        raise NotConnectedToOpenEdX(
            'To use this function, this package must be '
            'installed in an Open edX environment.'
        )
    course_id = CourseKey.from_string(course_key)
    course_grade = CourseGradeFactory().read(user, course_key=course_id, create_if_needed=False)
    return course_grade


def get_course_details(course_key):
    """
    Args:
        course_key (string): string course key
    Returns:
        course_overview: (openedx.core.djangoapps.content.course_overviews.models.CourseOverview)

    If there is a problem loading the CourseOverview class, throws NotConnectedToOpenEdX
    If issues with course_key string, throws a InvalidKeyError
    If course details not found, throws CourseOverview.DoesNotExist
    """
    if not CourseOverview:
        raise NotConnectedToOpenEdX(
            'To use this function, this package must be '
            'installed in an Open edX environment.'
        )
    course_id = CourseKey.from_string(course_key)
    course_overview = CourseOverview.get_from_id(course_id)
    return course_overview


def get_completion_summary(course_key, user):
    """
    Fetch completion summary for course + user using course blocks completions api
    Args:
        course_key (string): string course key
        user (django.contrib.auth.User): user instance
    Returns:
        object containing fields: complete_count, incomplete_count, locked_count

    If there is a problem loading the CourseOverview class, throws NotConnectedToOpenEdX
    If issues with course_key string, throws a InvalidKeyError
    If course details not found, throws CourseOverview.DoesNotExist
    """
    if not get_course_blocks_completion_summary:
        raise NotConnectedToOpenEdX(
            'To use get_course_blocks_completion_summary() function, this package must be '
            'installed in an Open edX environment.'
        )
    course_id = CourseKey.from_string(course_key)
    return get_course_blocks_completion_summary(course_id, user)
