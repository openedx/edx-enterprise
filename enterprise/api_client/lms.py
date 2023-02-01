"""
Utilities to get details from the course catalog API.
"""

import logging
import time
from urllib.parse import urljoin

from opaque_keys.edx.keys import CourseKey
from requests.exceptions import (  # pylint: disable=redefined-builtin
    ConnectionError,
    HTTPError,
    RequestException,
    Timeout,
)

from django.conf import settings

from enterprise.api_client.client import BackendServiceAPIClient, NoAuthAPIClient, UserAPIClient
from enterprise.constants import COURSE_MODE_SORT_ORDER, EXCLUDED_COURSE_MODES

try:
    from openedx.core.djangoapps.embargo import api as embargo_api
except ImportError:
    embargo_api = None


LOGGER = logging.getLogger(__name__)


class EmbargoApiClient:
    """
    Client interface for using the edx-platform embargo API.
    """

    @staticmethod
    def redirect_if_blocked(request, course_run_ids, user=None):
        """
        Return redirect to embargo error page if the given user is blocked.
        """
        for course_run_id in course_run_ids:
            redirect_url = embargo_api.redirect_if_blocked(
                request=request,
                course_key=CourseKey.from_string(course_run_id),
                user=user,
            )
            if redirect_url:
                return redirect_url
        return None


class EnrollmentApiClient(BackendServiceAPIClient):
    """
    The API client to make calls to the Enrollment API.
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
        api_url = self.get_api_url(f"course/{course_id}")
        try:
            response = self.client.get(api_url)
            response.raise_for_status()
            return response.json()
        except (RequestException, ConnectionError, Timeout):
            LOGGER.exception(
                'Failed to retrieve course enrollment details for course [%s].', course_id
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

    def enroll_user_in_course(self, username, course_id, mode, cohort=None, enterprise_uuid=None):
        """
        Call the enrollment API to enroll the user in the course specified by course_id.

        Args:
            username (str): The username by which the user goes on the OpenEdX platform
            course_id (str): The string value of the course's unique identifier
            mode (str): The enrollment mode which should be used for the enrollment
            cohort (str): Add the user to this named cohort
            enterprise_uuid (str): Add course enterprise uuid

        Returns:
            dict: A dictionary containing details of the enrollment, including course details, mode, username, etc.

        """
        api_url = self.get_api_url("enrollment")
        response = self.client.post(
            api_url,
            json={
                'user': username,
                'course_details': {'course_id': course_id},
                'is_active': True,
                'mode': mode,
                'cohort': cohort,
                'enterprise_uuid': str(enterprise_uuid)
            }
        )
        response.raise_for_status()
        return response.json()

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
            api_url = self.get_api_url("enrollment")
            response = self.client.post(
                api_url,
                json={
                    'user': username,
                    'course_details': {'course_id': course_id},
                    'is_active': False,
                    'mode': enrollment['mode']
                }
            )
            response.raise_for_status()
            return not response.json()['is_active']

        return False

    def update_course_enrollment_mode_for_user(self, username, course_id, mode):
        """
        Call the enrollment API to update a user's course enrollment to the specified mode, e.g. "audit".

        Args:
            username (str): The username by which the user goes on the OpenEdx platform
            course_id (str): The string value of the course's unique identifier
            mode (str): The string value of the course mode, e.g. "audit"

        Returns:
            dict: A dictionary containing details of the enrollment, including course details, mode, username, etc.
        """
        api_url = self.get_api_url("enrollment")
        response = self.client.post(
            api_url,
            json={
                'user': username,
                'course_details': {'course_id': course_id},
                'mode': mode,
            }
        )
        response.raise_for_status()
        return response.json()

    def get_course_enrollment(self, username, course_id):
        """
        Query the enrollment API to get information about a single course enrollment.

        Args:
            username (str): The username by which the user goes on the OpenEdX platform
            course_id (str): The string value of the course's unique identifier

        Returns:
            dict: A dictionary containing details of the enrollment, including course details, mode, username, etc.

        """
        username_course_string = '{username},{course_id}'.format(username=username, course_id=course_id)
        api_url = self.get_api_url(f"enrollment/{username_course_string}")

        try:
            response = self.client.get(api_url)
            response.raise_for_status()
        except HTTPError as err:
            # This enrollment data endpoint returns a 404 if either the username or course_id specified isn't valid
            if err.response.status_code == 404:
                LOGGER.error(
                    'Course enrollment details not found for invalid username or course; username=[%s], course=[%s]',
                    username,
                    course_id
                )
            return None
        # This enrollment data endpoint returns an empty string if the username and course_id is valid, but there's
        # no matching enrollment found
        if not response.content:
            LOGGER.info('Failed to find course enrollment details for user [%s] and course [%s]', username, course_id)
            return None

        return response.json()

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
        api_url = self.get_api_url("enrollment")
        response = self.client.get(api_url, params={"user": username})
        response.raise_for_status()
        return response.json()


class CourseApiClient(NoAuthAPIClient):
    """
    The API client to make calls to the Course API.
    """

    API_BASE_URL = urljoin(f"{settings.LMS_INTERNAL_ROOT_URL}/", "api/courses/v1/")
    APPEND_SLASH = True

    def get_course_details(self, course_id):
        """
        Retrieve all available details about a course.

        Args:
            course_id (str): The course ID identifying the course for which to retrieve details.

        Returns:
            dict: Contains keys identifying those course details available from the courses API (e.g., name).
        """
        api_url = self.get_api_url(f"courses/{course_id}")
        try:
            response = self.client.get(api_url)
            response.raise_for_status()
            return response.json()
        except (RequestException, ConnectionError, Timeout):
            LOGGER.exception('Details not found for course [%s].', course_id)
            return None


class ThirdPartyAuthApiClient(UserAPIClient):
    """
    The API client to make calls to the Third Party Auth API.
    """

    API_BASE_URL = urljoin(f"{settings.LMS_INTERNAL_ROOT_URL}/", "api/third_party_auth/v0/")

    @UserAPIClient.refresh_token
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

    @UserAPIClient.refresh_token
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
        api_url = self.get_api_url(f"providers/{identity_provider}/users")
        try:
            kwargs = {param_name: param_value}
            response = self.client.get(api_url, params=kwargs)
            response.raise_for_status()
            results = response.json().get('results', [])
        except HTTPError as err:
            if err.response.status_code == 404:
                LOGGER.error(
                    'Username not found for third party provider={%s}, {%s}={%s}',
                    identity_provider,
                    param_name,
                    param_value
                )
                results = []
            else:
                raise

        for row in results:
            if row.get(param_name) == param_value:
                return row.get(result_field_name)
        return None


class GradesApiClient(UserAPIClient):
    """
    The API client to make calls to the LMS Grades API.

    Note that this API client requires a JWT token, and so it keeps its token alive.
    """

    MAX_RETRIES = getattr(settings, "ENTERPRISE_DEGREED2_MAX_RETRIES", 4)
    API_BASE_URL = urljoin(f"{settings.LMS_INTERNAL_ROOT_URL}/", "api/grades/v1/")
    APPEND_SLASH = True

    def _calculate_backoff(self, attempt_count):
        """
        Calculate the seconds to sleep based on attempt_count
        """
        return (self.BACKOFF_FACTOR * (2 ** (attempt_count - 1)))

    @UserAPIClient.refresh_token
    def get_course_grade(self, course_id, username):
        """
        Retrieve the grade for the given username for the given course_id.

        Args:
        * ``course_id`` (str): The string value of the course's unique identifier
        * ``username`` (str): The username ID identifying the user for which to retrieve the grade.

        Raises:

        HTTPError if no grade found for the given user+course.

        Returns:

        a dict containing:

        * ``username``: A string representation of a user's username passed in the request.
        * ``course_key``: A string representation of a Course ID.
        * ``passed``: Boolean representing whether the course has been passed according the course's grading policy.
        * ``percent``: A float representing the overall grade for the course
        * ``letter_grade``: A letter grade as defined in grading_policy (e.g. 'A' 'B' 'C' for 6.002x) or None

        """
        api_url = self.get_api_url(f"courses/{course_id}")
        response = self.client.get(api_url, params={"username": username})
        response.raise_for_status()
        for row in response.json():
            if row.get('username') == username:
                return row

        raise HTTPError(f'No grade record found for course={course_id}, username={username}')

    @UserAPIClient.refresh_token
    def get_course_assessment_grades(self, course_id, username):
        """
        Retrieve the assessment grades for the given username for the given course_id.

        Args:
        * ``course_id`` (str): The string value of the course's unique identifier
        * ``username`` (str): The username ID identifying the user for which to retrieve the grade.

        Raises:

        HTTPError if no grade found for the given user+course.

        Returns:

        a list of dicts containing:

        * ``attempted``: A boolean representing whether the learner has attempted the subsection yet.
        * ``subsection_name``: String representation of the subsection's name.
        * ``category``: String representation of the subsection's category.
        * ``label``: String representation of the subsection's label.
        * ``score_possible``: The total amount of points that the learner could have earned on the subsection.
        * ``score_earned``: The total amount of points that the learner earned on the subsection.
        * ``percent``: A float representing the overall grade for the course.
        * ``module_id``: The ID of the subsection.
        """
        attempts = 0
        while True:
            attempts = attempts + 1
            api_url = self.get_api_url(f"gradebook/{course_id}")
            try:
                response = self.client.get(api_url, params={"username": username}, timeout=40)
                response.raise_for_status()
                break
            except Timeout as to_exception:
                if attempts <= self.MAX_RETRIES:
                    sleep_seconds = self._calculate_backoff(attempts)
                    LOGGER.warning(
                        f"[ATTEMPT: {attempts}] Request to the LMS grades API timeouted out with "
                        f"exception: {to_exception}, backing off for {sleep_seconds} seconds and retrying"
                    )
                    time.sleep(sleep_seconds)
                else:
                    LOGGER.warning(
                        f"Requests to the grades API has reached the max number of retries [{self.MAX_RETRIES}], "
                        f"attempting to retrieve grade data for learner: {username} under course {course_id}"
                    )
                    raise to_exception

        results = response.json()
        if results.get('username') == username:
            return results.get('section_breakdown')

        raise HTTPError(f"No assessment grade record found for course={course_id}, username={username}")


class CertificatesApiClient(UserAPIClient):
    """
    The API client to make calls to the LMS Certificates API.

    Note that this API client requires a JWT token, and so it keeps its token alive.
    """
    API_BASE_URL = urljoin(f"{settings.LMS_INTERNAL_ROOT_URL}/", "api/certificates/v0/")
    APPEND_SLASH = True

    @UserAPIClient.refresh_token
    def get_course_certificate(self, course_id, username):
        """
        Retrieve the certificate for the given username for the given course_id.

        Args:
        * ``course_id`` (str): The string value of the course's unique identifier
        * ``username`` (str): The username ID identifying the user for which to retrieve the certificate

        Returns:

        a dict containing:

        * ``username``: A string representation of an user's username passed in the request.
        * ``course_id``: A string representation of a Course ID.
        * ``certificate_type``: A string representation of the certificate type.
        * ``created_date``: Datetime the certificate was created (tz-aware).
        * ``status``: A string representation of the certificate status.
        * ``is_passing``: True if the certificate has a passing status, False if not.
        * ``download_url``: A string representation of the certificate url.
        * ``grade``: A string representation of a float for the user's course grade.

        """
        api_url = self.get_api_url(f"certificates/{username}/courses/{course_id}")
        response = self.client.get(api_url)
        response.raise_for_status()
        return response.json()


class NoAuthLMSClient(NoAuthAPIClient):
    """
    The LMS API client to make calls to the LMS without authentication.
    """

    API_BASE_URL = settings.LMS_INTERNAL_ROOT_URL
    APPEND_SLASH = False

    def get_health(self):
        """
        Retrieve health details for LMS service.

        Returns:
            dict: Response containing LMS service health.
        """
        api_url = self.get_api_url("heartbeat")
        response = self.client.get(api_url)
        response.raise_for_status()
        return response.json()
