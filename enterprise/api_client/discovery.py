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
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured, ObjectDoesNotExist
from django.utils.translation import ugettext_lazy as _

from enterprise import utils
from enterprise.utils import NotConnectedToOpenEdX, get_configuration_value_for_site

try:
    import cPickle as pickle
except ImportError:
    import pickle

try:
    from openedx.core.djangoapps.oauth_dispatch import jwt as JwtBuilder
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

    jwt = JwtBuilder.create_jwt_for_user(user)
    return EdxRestApiClient(catalog_url, jwt=jwt)


class CourseCatalogApiClient:
    """
    Object builds an API client to make calls to the Catalog API.
    """

    SEARCH_ALL_ENDPOINT = 'search/all/'
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
        self.catalog_url = get_configuration_value_for_site(
            site,
            'COURSE_CATALOG_API_URL',
            settings.COURSE_CATALOG_API_URL
        )
        self.client = course_discovery_api_client(user, self.catalog_url)

    @staticmethod
    def traverse_pagination(response, endpoint, content_filter_query, query_params):
        """
        Traverse a paginated API response and extracts and concatenates "results" returned by API.

        Arguments:
            response (dict): API response object.
            endpoint (Slumber.Resource): API endpoint object.
            content_filter_query (dict): query parameters used to filter catalog results.
            query_params (dict): query parameters used to paginate results.

        Returns:
            list: all the results returned by the API.
        """
        results = response.get('results', [])

        page = 1
        while response.get('next'):
            page += 1
            response = endpoint().post(content_filter_query, **dict(query_params, page=page))
            results += response.get('results', [])

        return results

    def get_catalog_results_from_discovery(self, content_filter_query, query_params=None, traverse_pagination=False):
        """
            Return results from the discovery service's search/all endpoint."""

        endpoint = getattr(self.client, self.SEARCH_ALL_ENDPOINT)
        response = endpoint().post(data=content_filter_query, **query_params)
        if traverse_pagination:
            response['results'] = self.traverse_pagination(response, endpoint, content_filter_query, query_params)
            response['next'] = response['previous'] = None
        return response

    def get_catalog_results(self, content_filter_query, query_params=None, traverse_pagination=False):
        """
            Return results from the cache or discovery service's search/all endpoint.
        Arguments:
            content_filter_query (dict): query parameters used to filter catalog results.
            query_params (dict): query parameters used to paginate results.
            traverse_pagination (bool): True to return all results, False to return the paginated response.
                                        Defaults to False.

        Returns:
            dict: Paginated response or all the records.
        """
        query_params = query_params or {}

        try:
            cache_key = utils.get_cache_key(
                service='discovery',
                endpoint=self.SEARCH_ALL_ENDPOINT,
                query=content_filter_query,
                traverse_pagination=traverse_pagination,
                **query_params
            )
            response = cache.get(cache_key)
            if not response:
                LOGGER.info(
                    'ENT-2390-1 | Calling discovery service for search/all/ '
                    'data with content_filter_query %s and query_params %s',
                    content_filter_query,
                    query_params,
                )
                # Response is not cached, so make a call.
                response = self.get_catalog_results_from_discovery(
                    content_filter_query,
                    query_params,
                    traverse_pagination
                )
                response_as_string = pickle.dumps(response)
                LOGGER.info(
                    'ENT-2489 | Response from content_filter_query %s is %d bytes long.',
                    content_filter_query,
                    len(response_as_string)
                )
                cache.set(cache_key, response, settings.ENTERPRISE_API_CACHE_TIMEOUT)
            else:
                LOGGER.info(
                    'ENT-2390-2 | Got search/all/ data from the cache with '
                    'content_filter_query %s and query_params %s',
                    content_filter_query,
                    query_params,
                )
        except Exception as ex:  # pylint: disable=broad-except
            LOGGER.exception(
                'Attempted to call course-discovery search/all/ endpoint with the following parameters: '
                'content_filter_query: %s, query_params: %s, traverse_pagination: %s. '
                'Failed to retrieve data from the catalog API. content -- [%s]',
                content_filter_query,
                query_params,
                traverse_pagination,
                getattr(ex, 'content', '')
            )
            # We need to bubble up failures when we encounter them instead of masking them!
            raise ex

        return response

    def get_course_id(self, course_identifier):
        """
        Return the course id for the given course identifier.  The `course_identifier` may be a course id or a course
        run id; in either case the course id will be returned.

        The 'course id' is the identifier for a course (ex. edX+DemoX)
        The 'course run id' is the identifier for a run of a course (ex. edX+DemoX+demo_run)

        Arguments:
            course_identifier (str): The course id or course run id

        Returns:
            (str): course id
        """

        try:
            CourseKey.from_string(course_identifier)
        except InvalidKeyError:
            # An `InvalidKeyError` is thrown if `course_identifier` is not in the proper format for a course run id.
            # Since `course_identifier` is not a course run id we assume `course_identifier` is the  course id.
            return course_identifier

        # If here, `course_identifier` must be a course run id.
        # We cannot use `CourseKey.from_string` to find the course id because that method assumes the course id is
        # always a substring of the course run id and this is not always the case.  The only reliable way to determine
        # which courses are associated with a given course run id is by by calling the discovery service.
        course_run_data = self.get_course_run(course_identifier)
        if 'course' in course_run_data:
            return course_run_data['course']

        LOGGER.info(
            "Could not find course_key for course identifier [%s].", course_identifier
        )
        return None

    def get_course_and_course_run(self, course_run_id):
        """
        Return the course and course run metadata for the given course run ID.

        Arguments:
            course_run_id (str): The course run ID.

        Returns:
            tuple: The course metadata and the course run metadata.
        """
        course_id = self.get_course_id(course_run_id)
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
            resource_id=course_run_id,
            long_term_cache=True
        )

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


def get_course_catalog_api_service_client(site=None):
    """
    Returns an instance of the CourseCatalogApiServiceClient

    Args:
        site: (Site)

    Returns:
        (CourseCatalogServiceClient)
    """
    return CourseCatalogApiServiceClient(site=site)


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
