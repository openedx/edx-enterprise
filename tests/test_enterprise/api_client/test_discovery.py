# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` course catalogs api module.
"""

import json
import logging
import unittest

import ddt
import mock
import responses
from six.moves.urllib.parse import urljoin  # pylint: disable=import-error
from slumber.exceptions import HttpClientError

from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured, ObjectDoesNotExist

from enterprise.api_client.discovery import CourseCatalogApiClient, CourseCatalogApiServiceClient
from enterprise.utils import NotConnectedToOpenEdX
from test_utils import MockLoggingHandler
from test_utils.fake_catalog_api import CourseDiscoveryApiTestMixin


class TestCourseCatalogApiInitialization(unittest.TestCase):
    """
    Test initialization of CourseCatalogAPI.
    """
    @mock.patch('enterprise.api_client.discovery.CatalogIntegration')
    @mock.patch('enterprise.api_client.discovery.get_edx_api_data')
    def test_raise_error_missing_course_discovery_api(self, *args):  # pylint: disable=unused-argument
        with self.assertRaises(NotConnectedToOpenEdX):
            CourseCatalogApiClient(mock.Mock(spec=User))

    @mock.patch('enterprise.api_client.discovery.JwtBuilder')
    @mock.patch('enterprise.api_client.discovery.get_edx_api_data')
    def test_raise_error_missing_catalog_integration(self, *args):  # pylint: disable=unused-argument
        with self.assertRaises(NotConnectedToOpenEdX):
            CourseCatalogApiClient(mock.Mock(spec=User))

    @mock.patch('enterprise.api_client.discovery.CatalogIntegration')
    @mock.patch('enterprise.api_client.discovery.JwtBuilder')
    def test_raise_error_missing_get_edx_api_data(self, *args):  # pylint: disable=unused-argument
        with self.assertRaises(NotConnectedToOpenEdX):
            CourseCatalogApiClient(mock.Mock(spec=User))


@ddt.ddt
class TestCourseCatalogApi(CourseDiscoveryApiTestMixin, unittest.TestCase):
    """
    Test course catalog API methods.
    """

    EMPTY_RESPONSES = (None, {}, [], set(), "")

    def setUp(self):
        super(TestCourseCatalogApi, self).setUp()
        self.user_mock = mock.Mock(spec=User)
        self.get_data_mock = self._make_patch(self._make_catalog_api_location("get_edx_api_data"))
        self.catalog_api_config_mock = self._make_patch(self._make_catalog_api_location("CatalogIntegration"))
        self.jwt_builder_mock = self._make_patch(self._make_catalog_api_location("JwtBuilder"))

        self.api = CourseCatalogApiClient(self.user_mock)

    @staticmethod
    def _make_course_run(key, *seat_types):
        """
        Return course_run json representation expected by CourseCatalogAPI.
        """
        return {
            "key": key,
            "seats": [{"type": seat_type} for seat_type in seat_types]
        }

    _make_run = _make_course_run.__func__  # unwrapping to use within class definition

    def test_get_course_details(self):
        """
        Verify get_course_details of CourseCatalogApiClient works as expected.
        """
        course_key = 'edX+DemoX'
        expected_result = {"complex": "dict"}
        self.get_data_mock.return_value = expected_result

        actual_result = self.api.get_course_details(course_key)

        assert self.get_data_mock.call_count == 1
        resource, resource_id = self._get_important_parameters(self.get_data_mock)

        assert resource == CourseCatalogApiClient.COURSES_ENDPOINT
        assert resource_id == 'edX+DemoX'
        assert actual_result == expected_result

    @ddt.data(*EMPTY_RESPONSES)
    def test_get_course_details_empty_response(self, response):
        """
        Verify get_course_details of CourseCatalogApiClient works as expected for empty responses.
        """
        self.get_data_mock.return_value = response
        assert self.api.get_course_details(course_id='edX+DemoX') == {}

    @ddt.data(
        "course-v1:JediAcademy+AppliedTelekinesis+T1",
        "course-v1:TrantorAcademy+Psychohistory101+T1",
        "course-v1:StarfleetAcademy+WarpspeedNavigation+T2337",
        "course-v1:SinhonCompanionAcademy+Calligraphy+TermUnknown",
        "course-v1:CampArthurCurrie+HeavyWeapons+T2245_5",
    )
    def test_get_course_run(self, course_run_id):
        """
        Verify get_course_run of CourseCatalogApiClient works as expected.
        """
        response_dict = {"very": "complex", "json": {"with": " nested object"}}
        self.get_data_mock.return_value = response_dict

        actual_result = self.api.get_course_run(course_run_id)

        assert self.get_data_mock.call_count == 1
        resource, resource_id = self._get_important_parameters(self.get_data_mock)

        assert resource == CourseCatalogApiClient.COURSE_RUNS_ENDPOINT
        assert resource_id is course_run_id
        assert actual_result == response_dict

    @ddt.data(*EMPTY_RESPONSES)
    def test_get_course_run_empty_response(self, response):
        """
        Verify get_course_run of CourseCatalogApiClient works as expected for empty responses.
        """
        self.get_data_mock.return_value = response
        assert self.api.get_course_run("any") == {}

    @ddt.data(
        "course-v1:JediAcademy+AppliedTelekinesis+T1",
        "course-v1:TrantorAcademy+Psychohistory101+T1",
    )
    def test_get_course_run_identifiers(self, course_run_id):

        self.get_data_mock.return_value = {}
        actual_result = self.api.get_course_run_identifiers(course_run_id)
        assert 'course_key' in actual_result
        assert actual_result['course_key'] is None
        assert 'course_uuid' in actual_result
        assert actual_result['course_uuid'] is None
        assert 'course_run_key' in actual_result
        assert actual_result['course_run_key'] is None
        assert 'course_run_uuid' in actual_result
        assert actual_result['course_run_uuid'] is None

        mock_response = {
            "key": "JediAcademy+AppliedTelekinesis",
            "uuid": "785b11f5-fad5-4ce1-9233-e1a3ed31aadb",
        }
        self.get_data_mock.return_value = mock_response
        actual_result = self.api.get_course_run_identifiers(course_run_id)
        assert 'course_key' in actual_result
        assert actual_result['course_key'] == 'JediAcademy+AppliedTelekinesis'
        assert 'course_uuid' in actual_result
        assert actual_result['course_uuid'] == '785b11f5-fad5-4ce1-9233-e1a3ed31aadb'
        assert 'course_run_key' in actual_result
        assert actual_result['course_run_key'] is None
        assert 'course_run_uuid' in actual_result
        assert actual_result['course_run_uuid'] is None

        mock_response = {
            "key": "JediAcademy+AppliedTelekinesis",
            "uuid": "785b11f5-fad5-4ce1-9233-e1a3ed31aadb",
            "course_runs": [],
        }
        self.get_data_mock.return_value = mock_response
        actual_result = self.api.get_course_run_identifiers(course_run_id)
        assert 'course_key' in actual_result
        assert actual_result['course_key'] == 'JediAcademy+AppliedTelekinesis'
        assert 'course_uuid' in actual_result
        assert actual_result['course_uuid'] == '785b11f5-fad5-4ce1-9233-e1a3ed31aadb'
        assert 'course_run_key' in actual_result
        assert actual_result['course_run_key'] is None
        assert 'course_run_uuid' in actual_result
        assert actual_result['course_run_uuid'] is None

        mock_response = {
            "key": "JediAcademy+AppliedTelekinesis",
            "uuid": "785b11f5-fad5-4ce1-9233-e1a3ed31aadb",
            "course_runs": [{
                "key": course_run_id,
                "uuid": "1234abcd-fad5-4ce1-9233-e1a3ed31aadb"
            }],
        }
        self.get_data_mock.return_value = mock_response
        actual_result = self.api.get_course_run_identifiers(course_run_id)
        assert 'course_key' in actual_result
        assert actual_result['course_key'] == 'JediAcademy+AppliedTelekinesis'
        assert 'course_uuid' in actual_result
        assert actual_result['course_uuid'] == '785b11f5-fad5-4ce1-9233-e1a3ed31aadb'
        assert 'course_run_key' in actual_result
        assert actual_result['course_run_key'] == course_run_id
        assert 'course_run_uuid' in actual_result
        assert actual_result['course_run_uuid'] == '1234abcd-fad5-4ce1-9233-e1a3ed31aadb'

    @ddt.data("Apollo", "Star Wars", "mk Ultra")
    def test_get_program_by_uuid(self, program_id):
        """
        Verify get_program_by_uuid of CourseCatalogApiClient works as expected.
        """
        response_dict = {"very": "complex", "json": {"with": " nested object"}}
        self.get_data_mock.return_value = response_dict

        actual_result = self.api.get_program_by_uuid(program_id)

        assert self.get_data_mock.call_count == 1
        resource, resource_id = self._get_important_parameters(self.get_data_mock)

        assert resource == CourseCatalogApiClient.PROGRAMS_ENDPOINT
        assert resource_id is program_id
        assert actual_result == response_dict

    @ddt.data(*EMPTY_RESPONSES)
    def test_get_program_by_uuid_empty_response(self, response):
        """
        Verify get_program_by_uuid of CourseCatalogApiClient works as expected for empty responses.
        """
        self.get_data_mock.return_value = response
        assert self.api.get_program_by_uuid("any") is None

    @ddt.data("MicroMasters Certificate", "Professional Certificate", "XSeries Certificate")
    def test_get_program_type_by_slug(self, slug):
        """
        Verify get_program_type_by_slug of CourseCatalogApiClient works as expected.
        """
        response_dict = {"very": "complex", "json": {"with": " nested object"}}
        self.get_data_mock.return_value = response_dict

        actual_result = self.api.get_program_type_by_slug(slug)

        assert self.get_data_mock.call_count == 1
        resource, resource_id = self._get_important_parameters(self.get_data_mock)

        assert resource == CourseCatalogApiClient.PROGRAM_TYPES_ENDPOINT
        assert resource_id is slug
        assert actual_result == response_dict

    @ddt.data(*EMPTY_RESPONSES)
    def test_get_program_type_by_slug_empty_response(self, response):
        """
        Verify get_program_type_by_slug of CourseCatalogApiClient works as expected for empty responses.
        """
        self.get_data_mock.return_value = response
        assert self.api.get_program_type_by_slug('slug') is None

    @ddt.data(
        (None, []),
        ({}, []),
        (
            {
                'courses': [
                    {'key': 'first+key'},
                    {'key': 'second+key'}
                ]
            },
            [
                'first+key',
                'second+key'
            ]
        )
    )
    @ddt.unpack
    def test_get_program_course_keys(self, response_body, expected_result):
        self.get_data_mock.return_value = response_body
        result = self.api.get_program_course_keys('fake-uuid')
        assert result == expected_result

    @ddt.data(
        (
            "course-v1:JediAcademy+AppliedTelekinesis+T1",
            {
                "course": "JediAcademy+AppliedTelekinesis"
            },
            {
                "course_runs": [{"key": "course-v1:JediAcademy+AppliedTelekinesis+T1"}]
            },
            "JediAcademy+AppliedTelekinesis",
            {"key": "course-v1:JediAcademy+AppliedTelekinesis+T1"}
        ),
        (
            "course-v1:JediAcademy+AppliedTelekinesis+T1",
            {},
            {},
            None,
            None
        ),
        (
            "course-v1:JediAcademy+AppliedTelekinesis+T1",
            {
                "course": "JediAcademy+AppliedTelekinesis"
            },
            {
                "course_runs": [
                    {"key": "course-v1:JediAcademy+AppliedTelekinesis+T222"},
                    {"key": "course-v1:JediAcademy+AppliedTelekinesis+T1"}
                ]
            },
            "JediAcademy+AppliedTelekinesis",
            {"key": "course-v1:JediAcademy+AppliedTelekinesis+T1"}
        ),
        (
            "course-v1:JediAcademy+AppliedTelekinesis+T1",
            {
                "course": "JediAcademy+AppliedTelekinesis"
            },
            {
                "course_runs": []
            },
            "JediAcademy+AppliedTelekinesis",
            None
        )
    )
    @ddt.unpack
    def test_get_course_and_course_run(
            self,
            course_run_id,
            course_runs_endpoint_response,
            course_endpoint_response,
            expected_resource_id,
            expected_course_run
    ):
        """
        Verify get_course_and_course_run of CourseCatalogApiClient works as expected.
        """
        self.get_data_mock.side_effect = [course_runs_endpoint_response, course_endpoint_response]
        expected_result = course_endpoint_response, expected_course_run

        actual_result = self.api.get_course_and_course_run(course_run_id)

        assert self.get_data_mock.call_count == 2
        resource, resource_id = self._get_important_parameters(self.get_data_mock)

        assert resource == CourseCatalogApiClient.COURSES_ENDPOINT
        assert resource_id == expected_resource_id
        assert actual_result == expected_result

    @ddt.data(*EMPTY_RESPONSES)
    def test_load_data_with_exception(self, default):
        """
        ``_load_data`` returns a default value given an exception.
        """
        self.get_data_mock.side_effect = HttpClientError
        assert self.api._load_data('', default=default) == default  # pylint: disable=protected-access

    @responses.activate
    def test_get_catalog_results(self):
        """
        Verify `get_catalog_results` of CourseCatalogApiClient works as expected.
        """
        content_filter_query = {'content_type': 'course', 'aggregation_key': ['course:edX+DemoX']}
        response_dict = {
            'next': 'next',
            'previous': 'previous',
            'results': [{
                'enterprise_id': 'a9e8bb52-0c8d-4579-8496-1a8becb0a79c',
                'catalog_id': 1111,
                'uuid': '785b11f5-fad5-4ce1-9233-e1a3ed31aadb',
                'aggregation_key': 'course:edX+DemoX',
                'content_type': 'course',
                'title': 'edX Demonstration Course',
            }],
        }
        responses.add(
            responses.POST,
            url=urljoin(self.api.catalog_url, self.api.SEARCH_ALL_ENDPOINT),
            json=response_dict,
            status=200,
        )
        actual_result = self.api.get_catalog_results(
            content_filter_query=content_filter_query,
            query_params={'page': 2}
        )
        assert actual_result == response_dict

    @responses.activate
    @mock.patch.object(CourseCatalogApiClient, 'get_catalog_results_from_discovery', return_value={'result': 'dummy'})
    def test_get_catalog_results_cache(self, mocked_get_catalog_results_from_discovery):  # pylint: disable=invalid-name
        """
        Verify `get_catalog_results` of CourseCatalogApiClient works as expected.
        """
        content_filter_query = {'content_type': 'course', 'aggregation_key': ['course:edX+DemoX']}
        self.api.get_catalog_results(content_filter_query=content_filter_query)
        assert mocked_get_catalog_results_from_discovery.call_count == 1

        # searching same query should not hit discovery service again
        self.api.get_catalog_results(content_filter_query=content_filter_query)
        assert mocked_get_catalog_results_from_discovery.call_count == 1

        # getting catalog with different params should hit discovery
        content_filter_query.update({'partner': 'edx'})
        self.api.get_catalog_results(content_filter_query=content_filter_query)
        assert mocked_get_catalog_results_from_discovery.call_count == 2

    @responses.activate
    def test_get_catalog_results_with_traverse_pagination(self):
        """
        Verify `get_catalog_results` of CourseCatalogApiClient works as expected with traverse_pagination=True.
        """
        content_filter_query = {'content_type': 'course', 'aggregation_key': ['course:edX+DemoX']}
        response_dict = {
            'next': 'next',
            'previous': None,
            'results': [{
                'enterprise_id': 'a9e8bb52-0c8d-4579-8496-1a8becb0a79c',
                'catalog_id': 1111,
                'uuid': '785b11f5-fad5-4ce1-9233-e1a3ed31aadb',
                'aggregation_key': 'course:edX+DemoX',
                'content_type': 'course',
                'title': 'edX Demonstration Course',
            }],
        }

        def request_callback(request):
            """
            Mocked callback for POST request to search/all endpoint.
            """
            response = response_dict
            if 'page=2' in request.url:
                response = dict(response, next=None)
            return (200, {}, json.dumps(response))

        responses.add_callback(
            responses.POST,
            url=urljoin(self.api.catalog_url, self.api.SEARCH_ALL_ENDPOINT),
            callback=request_callback,
            content_type='application/json',
        )
        responses.add_callback(
            responses.POST,
            url='{}?{}'.format(urljoin(self.api.catalog_url, self.api.SEARCH_ALL_ENDPOINT), '?page=2&page_size=100'),
            callback=request_callback,
            content_type='application/json',
        )

        recieved_response = self.api.get_catalog_results(
            content_filter_query=content_filter_query,
            traverse_pagination=True
        )
        complete_response = {
            'next': None,
            'previous': None,
            'results': response_dict['results'] * 2
        }

        assert recieved_response == complete_response

    @responses.activate
    def test_get_catalog_results_with_exception(self):
        """
        Verify `get_catalog_results` of CourseCatalogApiClient works as expected in case of exception.
        """
        responses.add(
            responses.POST,
            url=urljoin(self.api.catalog_url, self.api.SEARCH_ALL_ENDPOINT),
            body=HttpClientError(content='boom'),
        )
        logger = logging.getLogger('enterprise.api_client.discovery')
        handler = MockLoggingHandler(level="ERROR")
        logger.addHandler(handler)
        with self.assertRaises(HttpClientError):
            self.api.get_catalog_results(
                content_filter_query='query',
                query_params={u'page': 2}
            )
        expected_message = ('Attempted to call course-discovery search/all/ endpoint with the following parameters: '
                            'content_filter_query: query, query_params: {}, traverse_pagination: False. '
                            'Failed to retrieve data from the catalog API. content -- [boom]').format({u'page': 2})
        assert handler.messages['error'][0] == expected_message


class TestCourseCatalogApiServiceClientInitialization(unittest.TestCase):
    """
    Test initialization of CourseCatalogAPIServiceClient.
    """
    def test_raise_error_missing_catalog_integration(self, *args):  # pylint: disable=unused-argument
        with self.assertRaises(NotConnectedToOpenEdX):
            CourseCatalogApiServiceClient()

    @mock.patch('enterprise.api_client.discovery.CatalogIntegration')
    def test_raise_error_catalog_integration_disabled(self, mock_catalog_integration):
        mock_catalog_integration.current.return_value = mock.Mock(enabled=False)
        with self.assertRaises(ImproperlyConfigured):
            CourseCatalogApiServiceClient()

    @mock.patch('enterprise.api_client.discovery.CatalogIntegration')
    def test_raise_error_object_does_not_exist(self, mock_catalog_integration):
        mock_integration_config = mock.Mock(enabled=True)
        mock_integration_config.get_service_user.side_effect = ObjectDoesNotExist
        mock_catalog_integration.current.return_value = mock_integration_config
        with self.assertRaises(ImproperlyConfigured):
            CourseCatalogApiServiceClient()

    @mock.patch('enterprise.api_client.discovery.JwtBuilder')
    @mock.patch('enterprise.api_client.discovery.get_edx_api_data')
    @mock.patch('enterprise.api_client.discovery.CatalogIntegration')
    def test_success(self, mock_catalog_integration, *args):  # pylint: disable=unused-argument
        mock_integration_config = mock.Mock(enabled=True)
        mock_integration_config.get_service_user.return_value = mock.Mock(spec=User)
        mock_catalog_integration.current.return_value = mock_integration_config
        CourseCatalogApiServiceClient()


@ddt.ddt
class TestCourseCatalogApiService(CourseDiscoveryApiTestMixin, unittest.TestCase):
    """
    Tests for the CourseCatalogAPIServiceClient.
    """

    def setUp(self):
        """
        Set up mocks for the test suite.
        """
        super(TestCourseCatalogApiService, self).setUp()
        self.user_mock = mock.Mock(spec=User)
        self.get_data_mock = self._make_patch(self._make_catalog_api_location("get_edx_api_data"))
        self.jwt_builder_mock = self._make_patch(self._make_catalog_api_location("JwtBuilder"))
        self.integration_config_mock = mock.Mock(enabled=True)
        self.integration_config_mock.get_service_user.return_value = self.user_mock
        self.integration_mock = self._make_patch(self._make_catalog_api_location("CatalogIntegration"))
        self.integration_mock.current.return_value = self.integration_config_mock
        self.api = CourseCatalogApiServiceClient()

    @ddt.data({}, {'program': 'data'})
    def test_program_exists_no_exception(self, response):
        """
        The client should return the appropriate boolean value for program existence depending on the response.
        """
        self.get_data_mock.return_value = response
        assert CourseCatalogApiServiceClient.program_exists('a-s-d-f') == bool(response)

    def test_program_exists_with_exception(self):
        """
        The client should capture improper configuration for the class method and return False.
        """
        self.integration_mock.current.return_value.enabled = False
        assert not CourseCatalogApiServiceClient.program_exists('a-s-d-f')
