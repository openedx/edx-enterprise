"""
A utility collection for calls from integrated_channels to LMS APIs
If integrated_channels calls LMS APIs, put them here for better tracking.
"""
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey

try:
    from lms.djangoapps.certificates.api import get_certificate_for_user
    from lms.djangoapps.grades.course_grade_factory import CourseGradeFactory
    from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
    from openedx.core.djangoapps.content.course_overviews.models.CourseOverview import get_from_id
except ImportError:
    get_certificate_for_user = None
    CourseGradeFactory = None
    get_from_id = None
    CourseOverview = None

from enterprise.utils import NotConnectedToOpenEdX

# Constants
COURSE_OVERVIEW_NOT_FOUND = 'CourseOverview could not be found for course_key: {course_key}'
COURSE_KEY_INVALID = 'Invalid course_key: {course_key}'


def get_course_certificate(course_id, user):
    """
    A course certificate for a user (must be a django.contrib.auth.User instance).
    If there is a problem finding the course, throws a opaque_keys.InvalidKeyError
    If there is a problem loading the get_certificate_for_user function, throws NotConnectedToOpenEdX

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
    course_key = CourseKey.from_string(course_id)
    user_cert = get_certificate_for_user(username=user.username, course_key=course_key)
    return user_cert


def get_single_user_grade(course_id, user):
    """
    Returns a grade for the user (must be a django.contrib.auth.User instance).
    If there is a problem loading the CourseGradeFactory class, throws NotConnectedToOpenEdX

    Args:
        course_key (CourseLocator): The course to retrieve user grades for.

    Returns:
        A serializable list of grade responses
    """
    if not CourseGradeFactory:
        raise NotConnectedToOpenEdX(
            'To use this function, this package must be '
            'installed in an Open edX environment.'
        )
    course_key = CourseKey.from_string(course_id)
    course_grade = CourseGradeFactory().read(user, course_key=course_key)
    return course_grade


def get_course_details(course_id):
    """
    Returns:
        Tuple with values:
            course_overview or None
            error_code or None (if there is an error fetching course details)

    If there is a problem loading the CourseOverview class, throws NotConnectedToOpenEdX
    """
    if not get_from_id:
        raise NotConnectedToOpenEdX(
            'To use this function, this package must be '
            'installed in an Open edX environment.'
        )
    try:
        course_key = CourseKey.from_string(course_id)
        course_overview = get_from_id(course_key)
    except CourseOverview.DoesNotExist:
        return None, COURSE_OVERVIEW_NOT_FOUND.format(course_key=course_key)
    except InvalidKeyError:
        return None, COURSE_KEY_INVALID.format(course_key=course_key)
    else:
        return course_overview, None
