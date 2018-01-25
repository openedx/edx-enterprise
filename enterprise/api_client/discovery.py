# -*- coding: utf-8 -*-
"""
Utilities to get details from the course catalog API.
"""
from __future__ import absolute_import, unicode_literals

from logging import getLogger

from edx_rest_api_client.client import EdxRestApiClient
from edx_rest_api_client.exceptions import SlumberBaseException
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from requests.exceptions import ConnectionError, Timeout  # pylint: disable=redefined-builtin

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ObjectDoesNotExist
from django.utils.translation import ugettext_lazy as _

from enterprise.utils import (
    MultipleProgramMatchError,
    NotConnectedToOpenEdX,
    get_configuration_value_for_site,
    parse_course_key,
)

try:
    from openedx.core.lib.token_utils import JwtBuilder
except ImportError:
    JwtBuilder = None

try:
    from openedx.core.djangoapps.catalog.models import CatalogIntegration
except ImportError:
    CatalogIntegration = None

try:
    from openedx.core.lib.edx_api_utils import get_edx_api_data
except ImportError:
    get_edx_api_data = None


LOGGER = getLogger(__name__)


def course_discovery_api_client(user, catalog_url):
    """
    Return a Course Discovery API client setup with authentication for the specified user.
    """
    if JwtBuilder is None:
        raise NotConnectedToOpenEdX(
            _("To get a Catalog API client, this package must be "
              "installed in an Open edX environment.")
        )

    scopes = ['email', 'profile']
    expires_in = settings.OAUTH_ID_TOKEN_EXPIRATION
    jwt = JwtBuilder(user).build_token(scopes, expires_in)
    return EdxRestApiClient(catalog_url, jwt=jwt)


class CourseCatalogApiClient(object):
    """
    Object builds an API client to make calls to the Catalog API.
    """

    SEARCH_ALL_ENDPOINT = 'search/all/'
    CATALOGS_ENDPOINT = 'catalogs'
    CATALOGS_COURSES_ENDPOINT = 'catalogs/{}/courses/'
    COURSES_ENDPOINT = 'courses'
    COURSE_RUNS_ENDPOINT = 'course_runs'
    PROGRAMS_ENDPOINT = 'programs'
    PROGRAM_TYPES_ENDPOINT = 'program_types'

    DEFAULT_VALUE_SAFEGUARD = object()

    def __init__(self, user, site=None):
        """
        Create an Course Catalog API client setup with authentication for the specified user.

        This method retrieves an authenticated API client that can be used
        to access the course catalog API. It raises an exception to be caught at
        a higher level if the package doesn't have OpenEdX resources available.
        """
        if CatalogIntegration is None:
            raise NotConnectedToOpenEdX(
                _("To get a CatalogIntegration object, this package must be "
                  "installed in an Open edX environment.")
            )
        if get_edx_api_data is None:
            raise NotConnectedToOpenEdX(
                _("To parse a Catalog API response, this package must be "
                  "installed in an Open edX environment.")
            )

        self.user = user
        catalog_url = get_configuration_value_for_site(
            site,
            'COURSE_CATALOG_API_URL',
            settings.COURSE_CATALOG_API_URL
        )
        self.client = course_discovery_api_client(user, catalog_url)

    def get_search_results(self, querystring=None, traverse_pagination=True):
        """
        Return results from the discovery service's search/all endpoint.

        Arguments:
            querystring (dict): Querystring parameters used to filter search results.
            traverse_pagination (bool): True to return all results, False to return the paginated response.
                                        Defaults to True.
        Returns:
            list or dict: The paginated response dict if traverse_pagination is False, otherwise the extracted
                          results list.

        """
        return self._load_data(
            self.SEARCH_ALL_ENDPOINT,
            default=[],
            querystring=querystring,
            traverse_pagination=traverse_pagination,
            many=False,
        )

    def get_all_catalogs(self):
        """
        Return a list of all course catalogs, including name and ID.

        Returns:
            list: List of catalogs available for the user.

        """
        return self._load_data(
            self.CATALOGS_ENDPOINT,
            default=[]
        )

    def get_catalog(self, catalog_id):
        """
        Return specified course catalog.

        Returns:
            dict: catalog details if it is available for the user.

        """
        return self._load_data(
            self.CATALOGS_ENDPOINT,
            default=[],
            resource_id=catalog_id
        )

    def get_paginated_catalog_courses(self, catalog_id, querystring=None):
        """
        Return paginated response for all catalog courses.

        Returns:
            dict: API response with links to next and previous pages.

        """
        return self._load_data(
            self.CATALOGS_COURSES_ENDPOINT.format(catalog_id),
            default=[],
            querystring=querystring,
            traverse_pagination=False,
            many=False,
        )

    def get_paginated_catalogs(self, querystring=None):
        """
        Return a paginated list of course catalogs, including name and ID.

        Returns:
            dict: Paginated response containing catalogs available for the user.

        """
        return self._load_data(
            self.CATALOGS_ENDPOINT,
            default=[],
            querystring=querystring,
            traverse_pagination=False,
            many=False
        )

    def get_catalog_courses(self, catalog_id):
        """
        Return the courses included in a single course catalog by ID.

        Args:
            catalog_id (int): The catalog ID we want to retrieve.

        Returns:
            list: Courses of the catalog in question

        """
        return self._load_data(
            self.CATALOGS_COURSES_ENDPOINT.format(catalog_id),
            default=[]
        )

    def get_course_and_course_run(self, course_run_id):
        """
        Return the course and course run metadata for the given course run ID.

        Arguments:
            course_run_id (str): The course run ID.

        Returns:
            tuple: The course metadata and the course run metadata.
        """
        # Parse the course ID from the course run ID.
        course_id = parse_course_key(course_run_id)
        # Retrieve the course metadata from the catalog service.
        course = self.get_course_details(course_id)

        course_run = None
        if course:
            # Find the specified course run.
            course_run = None
            course_runs = [course_run for course_run in course['course_runs'] if course_run['key'] == course_run_id]
            if course_runs:
                course_run = course_runs[0]

        return course, course_run

    def get_course_details(self, course_id):
        """
        Return the details of a single course by id - not a course run id.

        Args:
            course_id (str): The unique id for the course in question.

        Returns:
            dict: Details of the course in question.

        """
        return self._load_data(
            self.COURSES_ENDPOINT,
            resource_id=course_id,
            many=False
        )

    def get_course_run(self, course_run_id):
        """
        Return course_run data, including name, ID and seats.

        Args:
            course_run_id(string): Course run ID (aka Course Key) in string format.

        Returns:
            dict: Course run data provided by Course Catalog API.

        """
        return self._load_data(
            self.COURSE_RUNS_ENDPOINT,
            resource_id=course_run_id
        )

    def get_program_by_title(self, program_title):
        """
        Return single program by name, or None if not found.

        Arguments:
            program_title(string): Program title as seen by students and in Course Catalog Admin

        Returns:
            dict: Program data provided by Course Catalog API

        """
        all_programs = self._load_data(self.PROGRAMS_ENDPOINT, default=[])
        matching_programs = [program for program in all_programs if program.get('title') == program_title]
        if len(matching_programs) > 1:
            raise MultipleProgramMatchError(len(matching_programs))
        elif len(matching_programs) == 1:
            return matching_programs[0]
        else:
            return None

    def get_program_by_uuid(self, program_uuid):
        """
        Return single program by UUID, or None if not found.

        Arguments:
            program_uuid(string): Program UUID in string form

        Returns:
            dict: Program data provided by Course Catalog API

        """
        return self._load_data(
            self.PROGRAMS_ENDPOINT,
            resource_id=program_uuid,
            default=None
        )

    def get_program_course_keys(self, program_uuid):
        """
        Get a list of the course IDs (not course run IDs) contained in the program.

        Arguments:
            program_uuid (str): Program UUID in string form

        Returns:
            list(str): List of course keys in string form that are included in the program

        """
        program_details = self.get_program_by_uuid(program_uuid)
        if not program_details:
            return []
        return [course['key'] for course in program_details.get('courses', [])]

    def get_program_type_by_slug(self, slug):
        """
        Get a program type by its slug.

        Arguments:
            slug (str): The slug to identify the program type.

        Returns:
            dict: A program type object.

        """
        return self._load_data(
            self.PROGRAM_TYPES_ENDPOINT,
            resource_id=slug,
            default=None,
        )

    def get_common_course_modes(self, course_run_ids):
        """
        Find common course modes for a set of course runs.

        This function essentially returns an intersection of types of seats available
        for each course run.

        Arguments:
            course_run_ids(Iterable[str]): Target Course run IDs.

        Returns:
            set: course modes found in all given course runs

        Examples:
            # run1 has prof and audit, run 2 has the same
            get_common_course_modes(['course-v1:run1', 'course-v1:run2'])
            {'prof', 'audit'}

            # run1 has prof and audit, run 2 has only prof
            get_common_course_modes(['course-v1:run1', 'course-v1:run2'])
            {'prof'}

            # run1 has prof and audit, run 2 honor
            get_common_course_modes(['course-v1:run1', 'course-v1:run2'])
            {}

            # run1 has nothing, run2 has prof
            get_common_course_modes(['course-v1:run1', 'course-v1:run2'])
            {}

            # run1 has prof and audit, run 2 prof, run3 has audit
            get_common_course_modes(['course-v1:run1', 'course-v1:run2', 'course-v1:run3'])
            {}

            # run1 has nothing, run 2 prof, run3 has prof
            get_common_course_modes(['course-v1:run1', 'course-v1:run2', 'course-v1:run3'])
            {}

        """
        available_course_modes = None
        for course_run_id in course_run_ids:
            course_run = self.get_course_run(course_run_id) or {}
            course_run_modes = {seat.get('type') for seat in course_run.get('seats', [])}

            if available_course_modes is None:
                available_course_modes = course_run_modes
            else:
                available_course_modes &= course_run_modes

            if not available_course_modes:
                return available_course_modes

        return available_course_modes

    def is_course_in_catalog(self, catalog_id, course_id):
        """
        Determine if the given course or course run ID is contained in the catalog with the given ID.

        Args:
            catalog_id (int): The ID of the catalog
            course_id (str): The ID of the course or course run

        Returns:
            bool: Whether the course or course run is contained in the given catalog
        """
        try:
            # Determine if we have a course run ID, rather than a plain course ID
            course_run_id = str(CourseKey.from_string(course_id))
        except InvalidKeyError:
            course_run_id = None

        endpoint = self.client.catalogs(catalog_id).contains

        if course_run_id:
            resp = endpoint.get(course_run_id=course_run_id)
        else:
            resp = endpoint.get(course_id=course_id)

        return resp.get('courses', {}).get(course_id, False)

    def _load_data(self, resource, default=DEFAULT_VALUE_SAFEGUARD, **kwargs):
        """
        Load data from API client.

        Arguments:
            resource(string): type of resource to load
            default(any): value to return if API query returned empty result. Sensible values: [], {}, None etc.

        Returns:
            dict: Deserialized response from Course Catalog API

        """
        default_val = default if default != self.DEFAULT_VALUE_SAFEGUARD else {}
        try:
            return get_edx_api_data(
                api_config=CatalogIntegration.current(),
                resource=resource,
                api=self.client,
                **kwargs
            ) or default_val
        except (SlumberBaseException, ConnectionError, Timeout) as exc:
            LOGGER.exception(
                'Failed to load data from resource [%s] with kwargs [%s] due to: [%s]',
                resource, kwargs, str(exc)
            )
            return default_val


class CourseCatalogApiServiceClient(CourseCatalogApiClient):
    """
    Catalog API client which uses the configured Catalog service user.
    """

    def __init__(self, site=None):
        """
        Create an Course Catalog API client setup with authentication for the
        configured catalog service user.
        """
        if CatalogIntegration is None:
            raise NotConnectedToOpenEdX(
                _("To get a CatalogIntegration object, this package must be "
                  "installed in an Open edX environment.")
            )

        catalog_integration = CatalogIntegration.current()
        if catalog_integration.enabled:
            try:
                user = catalog_integration.get_service_user()
                super(CourseCatalogApiServiceClient, self).__init__(user, site)
            except ObjectDoesNotExist:
                raise ImproperlyConfigured(_("The configured CatalogIntegration service user does not exist."))
        else:
            raise ImproperlyConfigured(_("There is no active CatalogIntegration."))

    @classmethod
    def program_exists(cls, program_uuid):
        """
        Get whether the program exists or not.
        """
        try:
            return bool(cls().get_program_by_uuid(program_uuid))
        except ImproperlyConfigured:
            return False
