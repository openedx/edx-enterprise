"""
A utility collection for calls from integrated_channels to LMS APIs
If integrated_channels calls LMS APIs, put them here for better tracking.
"""
from opaque_keys.edx.keys import CourseKey

try:
    from lms.djangoapps.certificates.api import get_certificate_for_user
    from lms.djangoapps.grades.course_grade_factory import CourseGradeFactory
    from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
except ImportError:
    get_certificate_for_user = None
    CourseGradeFactory = None
    CourseOverview = None

from enterprise.utils import NotConnectedToOpenEdX


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
    course_grade = CourseGradeFactory().read(user, course_key=course_id)
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
