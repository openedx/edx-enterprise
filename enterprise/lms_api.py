# -*- coding: utf-8 -*-
"""
Utilities to get details from the course catalog API.
"""
from __future__ import absolute_import, unicode_literals

import datetime
import logging
from functools import wraps
from time import time

import requests
from edx_rest_api_client.client import EdxRestApiClient
from slumber.exceptions import HttpNotFoundError

from django.conf import settings
from django.utils import timezone

from enterprise.utils import NotConnectedToOpenEdX

try:
    from opaque_keys.edx.keys import CourseKey
except ImportError:
    CourseKey = None

try:
    from student.models import CourseEnrollment
except ImportError:
    CourseEnrollment = None

try:
    from openedx.core.lib.token_utils import JwtBuilder
except ImportError:
    JwtBuilder = None


LOGGER = logging.getLogger(__name__)
LMS_API_DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%SZ'


class LmsApiClient(object):
    """
    Object builds an API client to make calls to the edxapp LMS API.

    Authenticates using settings.EDX_API_KEY.
    """

    API_BASE_URL = settings.LMS_ROOT_URL + '/api/'
    APPEND_SLASH = False

    def __init__(self):
        """
        Create an LMS API client, authenticated with the API token from Django settings.
        """
        session = requests.Session()
        session.headers = {"X-Edx-Api-Key": settings.EDX_API_KEY}
        self.client = EdxRestApiClient(
            self.API_BASE_URL, append_slash=self.APPEND_SLASH, session=session
        )


class JwtLmsApiClient(object):
    """
    LMS client authenticates using a JSON Web Token (JWT) for the given user.
    """

    API_BASE_URL = settings.LMS_ROOT_URL + '/api/'
    APPEND_SLASH = False

    def __init__(self, user, expires_in=settings.OAUTH_ID_TOKEN_EXPIRATION):
        """
        Connect to the REST API.
        """
        self.user = user
        self.expires_in = expires_in
        self.expires_at = 0
        self.client = None

    def connect(self):
        """
        Connect to the REST API, authenticating with a JWT for the current user.
        """
        if JwtBuilder is None:
            raise NotConnectedToOpenEdX("This package must be installed in an OpenEdX environment.")

        now = int(time())
        scopes = ['profile', 'email']
        jwt = JwtBuilder(self.user).build_token(scopes, self.expires_in)
        self.client = EdxRestApiClient(
            self.API_BASE_URL, append_slash=self.APPEND_SLASH, jwt=jwt,
        )
        self.expires_at = now + self.expires_in

    def token_expired(self):
        """
        Return True if the JWT token has expired, False if not.
        """
        return int(time()) > self.expires_at

    @staticmethod
    def refresh_token(func):
        """
        Method decorator that ensures the JWT token is refreshed when needed.
        """
        @wraps(func)
        def inner(self, *args, **kwargs):
            """
            Before calling the wrapped function, we check if the JWT token is expired, and if so, re-connect.
            """
            if self.token_expired():
                self.connect()
            return func(self, *args, **kwargs)
        return inner


class EnrollmentApiClient(LmsApiClient):
    """
    Object builds an API client to make calls to the Enrollment API.
    """

    API_BASE_URL = settings.ENTERPRISE_ENROLLMENT_API_URL

    def get_course_details(self, course_id):
        """
        Query the Enrollment API for the course details of the given course_id.

        Args:
            course_id (str): The string value of the course's unique identifier

        Returns:
            dict: A dictionary containing details about the course, in an enrollment context (allowed modes, etc.)
        """
        return self.client.course(course_id).get()

    def get_course_modes(self, course_id):
        """
        Query the Enrollment API for the specific course modes that are available for the given course_id.

        Arguments:
            course_id (str): The string value of the course's unique identifier

        Returns:
            list: A list of course mode dictionaries.
        """
        details = self.get_course_details(course_id)
        return details.get('course_modes', [])

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

    def get_course_enrollment(self, username, course_id):
        """
        Query the enrollment API to get information about a single course enrollment.

        Args:
            username (str): The username by which the user goes on the OpenEdX platform
            course_id (str): The string value of the course's unique identifier

        Returns:
            dict: A dictionary containing details of the enrollment, including course details, mode, username, etc.
        """
        endpoint = getattr(
            self.client.enrollment,
            '{username},{course_id}'.format(username=username, course_id=course_id)
        )
        try:
            result = endpoint.get()
        except HttpNotFoundError:
            # This enrollment data endpoint returns a 404 if either the username or course_id specified isn't valid
            LOGGER.error(
                'course enrollment details not found for invalid username or course; username=%s, course=%s',
                username,
                course_id
            )
            return None
        # This enrollment data endpoint returns an empty string if the username and course_id is valid, but there's
        # no matching enrollment found
        if not result:
            LOGGER.error('no course enrollment details found for username=%s, course=%s', username, course_id)
            return None

        return result

    def get_enrolled_courses(self, username):
        """
        Query the enrollment API to get a list of the courses a user is enrolled in.

        Args:
            username (str): The username by which the user goes on the OpenEdX platform

        Returns:
            list: A list of course objects, along with relevant user-specific enrollment details.
        """
        return self.client.enrollment.get(user=username)


class CourseApiClient(LmsApiClient):
    """
    Object builds an API client to make calls to the Course API.
    """

    API_BASE_URL = settings.LMS_ROOT_URL + '/api/courses/v1/'
    APPEND_SLASH = True

    def get_course_details(self, course_id):
        """
        Retrieve all available details about a course.

        Args:
            course_id (str): The course ID identifying the course for which to retrieve details.

        Returns:
            dict: Contains keys identifying those course details available from the courses API (e.g., name).
        """
        try:
            return self.client.courses(course_id).get()
        except HttpNotFoundError:
            LOGGER.error('details not found for course=%s', course_id)
            return None


class ThirdPartyAuthApiClient(LmsApiClient):
    """
    Object builds an API client to make calls to the Third Party Auth API.
    """

    API_BASE_URL = settings.LMS_ROOT_URL + '/api/third_party_auth/v0/'

    def get_remote_id(self, identity_provider, username):
        """
        Retrieve the remote identifier for the given username.

        Args:
        * ``identity_provider`` (str): identifier slug for the third-party authentication service used during SSO.
        * ``username`` (str): The username ID identifying the user for which to retrieve the remote name.

        Returns:
            string or None: the remote name of the given user.  None if not found.
        """
        try:
            returned = self.client.providers(identity_provider).users.get(username=username)
            results = returned.get('results', [])
        except HttpNotFoundError:
            LOGGER.error('remote_id not found for third party provider=%s, username=%s', identity_provider, username)
            results = []

        for row in results:
            if row.get('username') == username:
                return row.get('remote_id')
        return None


class GradesApiClient(JwtLmsApiClient):
    """
    Object builds an API client to make calls to the LMS Grades API.

    Note that this API client requires a JWT token, and so it keeps its token alive.
    """

    API_BASE_URL = settings.LMS_ROOT_URL + '/api/grades/v0/'
    APPEND_SLASH = True

    @JwtLmsApiClient.refresh_token
    def get_course_grade(self, course_id, username):
        """
        Retrieve the grade for the given username for the given course_id.

        Args:
        * ``course_id`` (str): The string value of the course's unique identifier
        * ``username`` (str): The username ID identifying the user for which to retrieve the grade.

        Raises:

        HttpNotFoundError if no grade found for the given user+course.

        Returns:

        a dict containing:

        * ``username``: A string representation of a user's username passed in the request.
        * ``course_key``: A string representation of a Course ID.
        * ``passed``: Boolean representing whether the course has been passed according the course's grading policy.
        * ``percent``: A float representing the overall grade for the course
        * ``letter_grade``: A letter grade as defined in grading_policy (e.g. 'A' 'B' 'C' for 6.002x) or None

        """
        results = self.client.course_grade(course_id).users().get(username=username)
        for row in results:
            if row.get('username') == username:
                return row

        raise HttpNotFoundError('No grade record found for course={}, username={}'.format(course_id, username))


class CertificatesApiClient(JwtLmsApiClient):
    """
    Object builds an API client to make calls to the LMS Certificates API.

    Note that this API client requires a JWT token, and so it keeps its token alive.
    """

    API_BASE_URL = settings.LMS_ROOT_URL + '/api/certificates/v0/'
    APPEND_SLASH = True

    @JwtLmsApiClient.refresh_token
    def get_course_certificate(self, course_id, username):
        """
        Retrieve the certificate for the given username for the given course_id.

        Args:
        * ``course_id`` (str): The string value of the course's unique identifier
        * ``username`` (str): The username ID identifying the user for which to retrieve the certificate

        Raises:

        HttpNotFoundError if no certificate found for the given user+course.

        Returns:

        a dict containing:

        * ``username``: A string representation of an user's username passed in the request.
        * ``course_id``: A string representation of a Course ID.
        * ``certificate_type``: A string representation of the certificate type.
        * ``created_date`: Datetime the certificate was created (tz-aware).
        * ``status``: A string representation of the certificate status.
        * ``is_passing``: True if the certificate has a passing status, False if not.
        * ``download_url``: A string representation of the certificate url.
        * ``grade``: A string representation of a float for the user's course grade.
        """
        return self.client.certificates(username).courses(course_id).get()


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
        raise NotConnectedToOpenEdX("This package must be installed in an OpenEdX environment.")
    CourseEnrollment.enroll(user, CourseKey.from_string(course_id), mode=mode, check_access=True)


def parse_lms_api_datetime(datetime_string, datetime_format=LMS_API_DATETIME_FORMAT):
    """
    Parse a received datetime into a timezone-aware, Python datetime object.

    Arguments:
        datetime_string: A string to be parsed.
        datetime_format: A datetime format string to be used for parsing
    """
    if isinstance(datetime_string, datetime.datetime):
        date_time = datetime_string
    else:
        date_time = datetime.datetime.strptime(datetime_string, datetime_format)

    # If the datetime format didn't include a timezone, then set to UTC.
    # Note that if we're using the default LMS_API_DATETIME_FORMAT, it ends in 'Z',
    # which denotes UTC for ISO-8661.
    if date_time.tzinfo is None:
        date_time = date_time.replace(tzinfo=timezone.utc)
    return date_time
