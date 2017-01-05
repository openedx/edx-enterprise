# -*- coding: utf-8 -*-
"""
Utilities to get details from the course catalog API.
"""
from __future__ import absolute_import, unicode_literals

import requests
from edx_rest_api_client.client import EdxRestApiClient

from django.conf import settings

from enterprise.utils import NotConnectedToEdX

try:
    from opaque_keys.edx.keys import CourseKey
except ImportError:
    CourseKey = None

try:
    from student.models import CourseEnrollment
except ImportError:
    CourseEnrollment = None


class EnrollmentApiClient(object):
    """
    Object builds an API client to make calls to the Enrollment API.
    """

    def __init__(self):
        """
        Create an Enrollment API client, authenticated with the API token from Django settings.
        """
        session = requests.Session()
        session.headers = {"X-Edx-Api-Key": settings.EDX_API_KEY}
        self.client = EdxRestApiClient(
            settings.ENTERPRISE_ENROLLMENT_API_URL, append_slash=False, session=session
        )

    def get_course_details(self, course_id):
        """
        Query the Enrollment API for the course details of the given course_id.

        Args:
            course_id (str): The string value of the course's unique identifier

        Returns:
            dict: A dictionary containing details about the course, in an enrollment context (allowed modes, etc.)
        """
        return self.client.course(course_id).get()

    def enroll_user_in_course(self, username, course_id, mode):
        """
        Call the enrollment API to enroll the user in the course specified by course_id.

        Args:
            username (str): The username by which the user goes on the OpenEdX platform
            course_id (str): The string value of the course's unique identifier
            mode (str): The enrollment mode which should be used for the enrollment

        Returns:
            dict: A dictionary containing details of the enrollment, including course details, mode, username, etc.
        """
        return self.client.enrollment.post(
            {
                'user': username,
                'course_details': {'course_id': course_id},
                'mode': mode,
            }
        )

    def get_enrolled_courses(self, username):
        """
        Query the enrollment API to get a list of the courses a user is enrolled in.

        Args:
            username (str): The username by which the user goes on the OpenEdX platform

        Returns:
            list: A list of course objects, along with relevant user-specific enrollment details.
        """
        return self.client.enrollment.get(user=username)


class CourseApiClient(object):
    """
    Object builds an API client to make calls to the Course API.
    """

    def __init__(self):
        """
        Create a Courses API client, authenticated with the API token from Django settings.
        """
        session = requests.Session()
        session.headers = {'X-Edx-Api-Key': settings.EDX_API_KEY}
        self.client = EdxRestApiClient(
            settings.LMS_ROOT_URL + '/api/courses/v1/',
            append_slash=True,
            session=session,
        )

    def get_course_details(self, course_id):
        """
        Retrieve all available details about a course.

        Args:
            course_id (str): The course ID identifying the course for which to retrieve details.

        Returns:
            dict: Contains keys identifying those course details available from the courses API (e.g., name).
        """
        return self.client.courses(course_id).get()


def enroll_user_in_course_locally(user, course_id, mode):
    """
    Enroll a user in a course, using local database methods.

    This is only used in one place; in models.py. It is necessary
    because the enrollment API can't enroll a user before it exists, and
    the post_save signal for users results in a user not actually being
    saved until after the API call is made.

    In Django 1.9 and later, there's a transaction.on_commit hook that we can
    use to create a callback. Once we're able to depend on having Django 1.9, we
    can shift over to that, but for right now, we have to do it this way.
    """
    if CourseKey is None and CourseEnrollment is None:
        raise NotConnectedToEdX("This package must be installed in an OpenEdX environment.")
    CourseEnrollment.enroll(user, CourseKey.from_string(course_id), mode=mode, check_access=True)
