"""
A utility collection for calls from integrated_channels to LMS APIs
If integrated_channels calls LMS APIs, put them here for better tracking.
"""
from opaque_keys.edx.keys import CourseKey

try:
    from lms.djangoapps.certificates.api import get_certificate_for_user
except ImportError:
    get_certificate_for_user = None


def get_course_certificate(course_id, username):
    """
    A course certificate for a user.
    If there is a problem finding the course, throws a opaque_keys.InvalidKeyError

    Returns dict, for example:
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
        return None
    course_key = CourseKey.from_string(course_id)
    user_cert = get_certificate_for_user(username=username, course_key=course_key)
    return user_cert
