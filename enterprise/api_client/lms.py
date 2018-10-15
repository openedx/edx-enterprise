# -*- coding: utf-8 -*-
"""
Utilities to get details from the course catalog API.
"""
from __future__ import absolute_import, unicode_literals

import datetime
import logging
from functools import wraps
from time import time

from edx_rest_api_client.client import EdxRestApiClient
from opaque_keys.edx.keys import CourseKey
from requests import Session
from requests.exceptions import ConnectionError, Timeout  # pylint: disable=redefined-builtin
from slumber.exceptions import HttpNotFoundError, SlumberBaseException

from django.conf import settings
from django.utils import timezone

from enterprise.constants import COURSE_MODE_SORT_ORDER, EXCLUDED_COURSE_MODES
from enterprise.utils import NotConnectedToOpenEdX

try:
    from openedx.core.djangoapps.embargo import api as embargo_api
except ImportError:
    embargo_api = None

try:
    from openedx.core.djangoapps.oauth_dispatch import jwt as JwtBuilder
except ImportError:
    JwtBuilder = None


LOGGER = logging.getLogger(__name__)
LMS_API_DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%SZ'
LMS_API_DATETIME_FORMAT_WITHOUT_TIMEZONE = '%Y-%m-%dT%H:%M:%S'


class LmsApiClient(object):
    """
    Object builds an API client to make calls to the edxapp LMS API.

    Authenticates using settings.EDX_API_KEY.
    """

    API_BASE_URL = settings.LMS_INTERNAL_ROOT_URL + '/api/'
    APPEND_SLASH = False

    def __init__(self):
        """
        Create an LMS API client, authenticated with the API token from Django settings.
        """
        session = Session()
        session.headers = {"X-Edx-Api-Key": settings.EDX_API_KEY}
        self.client = EdxRestApiClient(
            self.API_BASE_URL, append_slash=self.APPEND_SLASH, session=session
        )


class JwtLmsApiClient(object):
    """
    LMS client authenticates using a JSON Web Token (JWT) for the given user.
    """

    API_BASE_URL = settings.LMS_INTERNAL_ROOT_URL + '/api/'
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
        jwt = JwtBuilder.create_jwt_for_user(self.user)
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
        Use this method decorator to ensure the JWT token is refreshed when needed.
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


class EmbargoApiClient(object):
    """
    Client interface for using the edx-platform embargo API.
    """

    @staticmethod
    def redirect_if_blocked(course_run_ids, user=None, ip_address=None, url=None):
        """
        Return redirect to embargo error page if the given user is blocked.
        """
        for course_run_id in course_run_ids:
            redirect_url = embargo_api.redirect_if_blocked(
                CourseKey.from_string(course_run_id),
                user=user,
                ip_address=ip_address,
                url=url
            )
            if redirect_url:
                return redirect_url


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
        try:
            return self.client.course(course_id).get()
        except (SlumberBaseException, ConnectionError, Timeout) as exc:
            LOGGER.exception(
                'Failed to retrieve course enrollment details for course [%s] due to: [%s]',
                course_id, str(exc)
            )
            return {}

    def _sort_course_modes(self, modes):
        """
        Sort the course mode dictionaries by slug according to the COURSE_MODE_SORT_ORDER constant.

        Arguments:
            modes (list): A list of course mode dictionaries.
        Returns:
            list: A list with the course modes dictionaries sorted by slug.

        """
        def slug_weight(mode):
            """
            Assign a weight to the course mode dictionary based on the position of its slug in the sorting list.
            """
            sorting_slugs = COURSE_MODE_SORT_ORDER
            sorting_slugs_size = len(sorting_slugs)
            if mode['slug'] in sorting_slugs:
                return sorting_slugs_size - sorting_slugs.index(mode['slug'])
            return 0
        # Sort slug weights in descending order
        return sorted(modes, key=slug_weight, reverse=True)

    def get_course_modes(self, course_id):
        """
        Query the Enrollment API for the specific course modes that are available for the given course_id.

        Arguments:
            course_id (str): The string value of the course's unique identifier

        Returns:
            list: A list of course mode dictionaries.

        """
        details = self.get_course_details(course_id)
        modes = details.get('course_modes', [])
        return self._sort_course_modes([mode for mode in modes if mode['slug'] not in EXCLUDED_COURSE_MODES])

    def has_course_mode(self, course_run_id, mode):
        """
        Query the Enrollment API to see whether a course run has a given course mode available.

        Arguments:
            course_run_id (str): The string value of the course run's unique identifier

        Returns:
            bool: Whether the course run has the given mode avaialble for enrollment.

        """
        course_modes = self.get_course_modes(course_run_id)
        return any(course_mode for course_mode in course_modes if course_mode['slug'] == mode)

    def enroll_user_in_course(self, username, course_id, mode, cohort=None):
        """
        Call the enrollment API to enroll the user in the course specified by course_id.

        Args:
            username (str): The username by which the user goes on the OpenEdX platform
            course_id (str): The string value of the course's unique identifier
            mode (str): The enrollment mode which should be used for the enrollment
            cohort (str): Add the user to this named cohort

        Returns:
            dict: A dictionary containing details of the enrollment, including course details, mode, username, etc.

        """
        return self.client.enrollment.post(
            {
                'user': username,
                'course_details': {'course_id': course_id},
                'mode': mode,
                'cohort': cohort,
            }
        )

    def unenroll_user_from_course(self, username, course_id):
        """
        Call the enrollment API to unenroll the user in the course specified by course_id.
        Args:
            username (str): The username by which the user goes on the OpenEdx platform
            course_id (str): The string value of the course's unique identifier
        Returns:
            bool: Whether the unenrollment succeeded
        """
        enrollment = self.get_course_enrollment(username, course_id)
        if enrollment and enrollment['is_active']:
            response = self.client.enrollment.post({
                'user': username,
                'course_details': {'course_id': course_id},
                'is_active': False,
                'mode': enrollment['mode']
                })
            return not response['is_active']

        return False

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
                'Course enrollment details not found for invalid username or course; username=[%s], course=[%s]',
                username,
                course_id
            )
            return None
        # This enrollment data endpoint returns an empty string if the username and course_id is valid, but there's
        # no matching enrollment found
        if not result:
            LOGGER.info('Failed to find course enrollment details for user [%s] and course [%s]', username, course_id)
            return None

        return result

    def is_enrolled(self, username, course_run_id):
        """
        Query the enrollment API and determine if a learner is enrolled in a course run.

        Args:
            username (str): The username by which the user goes on the OpenEdX platform
            course_run_id (str): The string value of the course's unique identifier

        Returns:
            bool: Indicating whether the user is enrolled in the course run. Returns False under any errors.

        """
        enrollment = self.get_course_enrollment(username, course_run_id)
        return enrollment is not None and enrollment.get('is_active', False)

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

    API_BASE_URL = settings.LMS_INTERNAL_ROOT_URL + '/api/courses/v1/'
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
        except (SlumberBaseException, ConnectionError, Timeout) as exc:
            LOGGER.exception('Details not found for course [%s] due to: [%s]', course_id, str(exc))
            return None


class ThirdPartyAuthApiClient(LmsApiClient):
    """
    Object builds an API client to make calls to the Third Party Auth API.
    """

    API_BASE_URL = settings.LMS_INTERNAL_ROOT_URL + '/api/third_party_auth/v0/'

    def get_remote_id(self, identity_provider, username):
        """
        Retrieve the remote identifier for the given username.

        Args:
        * ``identity_provider`` (str): identifier slug for the third-party authentication service used during SSO.
        * ``username`` (str): The username ID identifying the user for which to retrieve the remote name.

        Returns:
            string or None: the remote name of the given user.  None if not found.
        """
        return self._get_results(identity_provider, 'username', username, 'remote_id')

    def get_username_from_remote_id(self, identity_provider, remote_id):
        """
        Retrieve the remote identifier for the given username.

        Args:
        * ``identity_provider`` (str): identifier slug for the third-party authentication service used during SSO.
        * ``remote_id`` (str): The remote id identifying the user for which to retrieve the usernamename.

        Returns:
            string or None: the username of the given user.  None if not found.
        """
        return self._get_results(identity_provider, 'remote_id', remote_id, 'username')

    def _get_results(self, identity_provider, param_name, param_value, result_field_name):
        """
        Calls the third party auth api endpoint to get the mapping between usernames and remote ids.
        """
        try:
            kwargs = {param_name: param_value}
            returned = self.client.providers(identity_provider).users.get(**kwargs)
            results = returned.get('results', [])
        except HttpNotFoundError:
            LOGGER.error(
                'username not found for third party provider={provider}, {querystring_param}={id}'.format(
                    provider=identity_provider,
                    querystring_param=param_name,
                    id=param_value
                )
            )
            results = []

        for row in results:
            if row.get(param_name) == param_value:
                return row.get(result_field_name)
        return None


class GradesApiClient(JwtLmsApiClient):
    """
    Object builds an API client to make calls to the LMS Grades API.

    Note that this API client requires a JWT token, and so it keeps its token alive.
    """

    API_BASE_URL = settings.LMS_INTERNAL_ROOT_URL + '/api/grades/v0/'
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

    API_BASE_URL = settings.LMS_INTERNAL_ROOT_URL + '/api/certificates/v0/'
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
        try:
            date_time = datetime.datetime.strptime(datetime_string, datetime_format)
        except ValueError:
            date_time = datetime.datetime.strptime(datetime_string, LMS_API_DATETIME_FORMAT_WITHOUT_TIMEZONE)

    # If the datetime format didn't include a timezone, then set to UTC.
    # Note that if we're using the default LMS_API_DATETIME_FORMAT, it ends in 'Z',
    # which denotes UTC for ISO-8661.
    if date_time.tzinfo is None:
        date_time = date_time.replace(tzinfo=timezone.utc)
    return date_time
