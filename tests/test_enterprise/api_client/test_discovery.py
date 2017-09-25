# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` course catalogs api module.
"""

from __future__ import absolute_import, unicode_literals, with_statement

import unittest

import ddt
import mock
from pytest import raises
from slumber.exceptions import HttpClientError

from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured, ObjectDoesNotExist

from enterprise.api_client.discovery import CourseCatalogApiClient, CourseCatalogApiServiceClient
from enterprise.utils import CourseCatalogApiError, NotConnectedToOpenEdX
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

    def test_get_search_results(self):
        """
        Verify get_search_results of CourseCatalogApiClient works as expected.
        """
        querystring = 'very'
        response_dict = {"very": "complex", "json": {"with": " nested object"}}
        self.get_data_mock.return_value = response_dict
        actual_result = self.api.get_search_results(querystring=querystring)
        assert self.get_data_mock.call_count == 1
        resource, resource_id = self._get_important_parameters(self.get_data_mock)
        assert resource == CourseCatalogApiClient.SEARCH_ALL_ENDPOINT
        assert resource_id is None
        assert actual_result == response_dict

    @ddt.data(*EMPTY_RESPONSES)
    def test_get_search_results_empty_response(self, response):
        """
        Verify get_search_results of CourseCatalogApiClient works as expected for empty responses.
        """
        self.get_data_mock.return_value = response
        assert self.api.get_search_results(querystring='querystring') == []

    def test_get_all_catalogs(self):
        """
        Verify get_all_catalogs of CourseCatalogApiClient works as expected.
        """
        response_dict = {"very": "complex", "json": {"with": " nested object"}}
        self.get_data_mock.return_value = response_dict

        actual_result = self.api.get_all_catalogs()

        assert self.get_data_mock.call_count == 1
        resource, resource_id = self._get_important_parameters(self.get_data_mock)

        assert resource == CourseCatalogApiClient.CATALOGS_ENDPOINT
        assert resource_id is None
        assert actual_result == response_dict

    @ddt.data(*EMPTY_RESPONSES)
    def test_get_all_catalogs_empty_response(self, response):
        """
        Verify get_all_catalogs of CourseCatalogApiClient works as expected for empty responses.
        """
        self.get_data_mock.return_value = response
        assert self.api.get_all_catalogs() == []

    def test_get_catalog_courses(self):
        """
        Verify get_catalog_courses of CourseCatalogApiClient works as expected.
        """
        catalog_id = 123
        expected_result = ['item1', 'item2', 'item3']
        self.get_data_mock.return_value = expected_result

        actual_result = self.api.get_catalog_courses(catalog_id)

        assert self.get_data_mock.call_count == 1
        resource, _ = self._get_important_parameters(self.get_data_mock)

        assert resource == CourseCatalogApiClient.CATALOGS_COURSES_ENDPOINT.format(catalog_id)
        assert actual_result == expected_result

    @ddt.data(*EMPTY_RESPONSES)
    def test_get_catalog_courses_empty_response(self, response):
        """
        Verify get_catalog_courses of CourseCatalogApiClient works as expected for empty responses.
        """
        self.get_data_mock.return_value = response
        assert self.api.get_catalog_courses(catalog_id=1) == []

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

    def test_get_catalog(self):
        """
        Verify get_catalog of CourseCatalogApiClient works as expected.
        """
        response_dict = {"very": "complex", "json": {"with": " nested object"}}
        self.get_data_mock.return_value = response_dict

        actual_result = self.api.get_catalog(catalog_id=1)

        assert self.get_data_mock.call_count == 1
        resource, resource_id = self._get_important_parameters(self.get_data_mock)

        assert resource == CourseCatalogApiClient.CATALOGS_ENDPOINT
        assert resource_id is 1
        assert actual_result == response_dict

    @ddt.data(*EMPTY_RESPONSES)
    def test_get_catalog_empty_response(self, response):
        """
        Verify get_catalog of CourseCatalogApiClient works as expected.
        """
        self.get_data_mock.return_value = response
        assert self.api.get_catalog(catalog_id=1) == []

    def test_get_paginated_catalog_courses(self):
        """
        Verify get_paginated_catalog_courses of CourseCatalogApiClient works as expected.
        """
        catalog_id = 1
        response_dict = {"very": "complex", "json": {"with": " nested object"}}
        self.get_data_mock.return_value = response_dict

        actual_result = self.api.get_paginated_catalog_courses(catalog_id=catalog_id)

        assert self.get_data_mock.call_count == 1
        resource, resource_id = self._get_important_parameters(self.get_data_mock)

        assert resource == CourseCatalogApiClient.CATALOGS_COURSES_ENDPOINT.format(catalog_id)
        assert resource_id is None
        assert actual_result == response_dict

    @ddt.data(*EMPTY_RESPONSES)
    def test_get_paginated_catalog_courses_empty_response(self, response):
        """
        Verify get_paginated_catalog_courses of CourseCatalogApiClient works as expected.
        """
        self.get_data_mock.return_value = response
        assert self.api.get_paginated_catalog_courses(catalog_id=1) == []

    def test_get_paginated_catalogs(self):
        """
        Verify get_paginated_catalogs of CourseCatalogApiClient works as expected.
        """
        response_dict = {'very': 'complex', 'json': {'with': 'nested object'}}
        self.get_data_mock.return_value = response_dict

        actual_result = self.api.get_paginated_catalogs()

        resource, resource_id = self._get_important_parameters(self.get_data_mock)

        assert resource == CourseCatalogApiClient.CATALOGS_ENDPOINT
        assert resource_id is None
        assert actual_result == response_dict

    @ddt.data(*EMPTY_RESPONSES)
    def test_get_paginated_catalogs_empty_response(self, response):
        """
        Verify get_paginated_catalogs of CourseCatalogApiClient works as expected for an empty response.
        """
        self.get_data_mock.return_value = response
        assert self.api.get_paginated_catalog_courses(catalog_id=1) == []

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

    @ddt.unpack
    @ddt.data(
        ("mk Ultra", [{'title': "Star Wars"}], None),
        ("Star Wars", [{'title': "Star Wars"}], {'title': "Star Wars"}),
        (
            "Apollo",
            [{'title': "Star Wars"}, {'title': "Apollo", "uuid": "Apollo11"}],
            {'title': "Apollo", "uuid": "Apollo11"}
        ),
    )
    def test_get_program_by_title(self, program_title, response, expected_result):
        """
        Verify get_program_by_title of CourseCatalogApiClient works as expected.
        """
        self.get_data_mock.return_value = response

        actual_result = self.api.get_program_by_title(program_title)

        assert self.get_data_mock.call_count == 1
        resource, _ = self._get_important_parameters(self.get_data_mock)

        assert resource == CourseCatalogApiClient.PROGRAMS_ENDPOINT
        assert actual_result == expected_result

    @ddt.data(*EMPTY_RESPONSES)
    def test_get_program_by_title_empty_response(self, response):
        """
        Verify get_program_by_title of CourseCatalogApiClient works as expected for empty responses.
        """
        self.get_data_mock.return_value = response
        assert self.api.get_program_by_title("any") is None

    def test_get_program_by_title_raise_multiple_match(self):
        """
        Verify get_program_by_title of CourseCatalogApiClient works as expected for when there are multiple matches.
        """
        self.get_data_mock.return_value = [
            {'title': "Apollo", "uuid": "Apollo11"},
            {'title': "Apollo", "uuid": "Apollo12"}
        ]
        with raises(CourseCatalogApiError):
            self.api.get_program_by_title("Apollo")

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

    @ddt.unpack
    @ddt.data(
        # single run
        (("c1",), [_make_run("c1", "prof", "audit")], {"prof", "audit"}),
        # multiple runs - intersection
        (("c1", "c2"), [_make_run("c1", "prof", "audit"), _make_run("c2", "prof")], {"prof"}),
        # multiple runs, one of which is empty
        (("c1", "c2"), [_make_run("c1"), _make_run("c2", "prof")], set()),
        # multiple runs, one of which is empty - other way around
        (("c1", "c2"), [_make_run("c2", "prof"), _make_run("c1")], set()),
        # run(s) not found
        (("c1", "c3", "c4"), [_make_run("c1"), _make_run("c2", "prof")], set()),
    )
    def test_get_common_course_modes(self, course_runs, response, expected_result):
        """
        Verify get_common_course_modes of CourseCatalogApiClient works as expected.
        """
        def get_course_run(*args, **kwargs):  # pylint: disable=unused-argument
            """
            Return course run data from `reponse` argument by key.
            """
            resource_id = kwargs.get("resource_id")
            try:
                return next(item for item in response if item["key"] == resource_id)
            except StopIteration:
                return {}

        self.get_data_mock.side_effect = get_course_run

        actual_result = self.api.get_common_course_modes(course_runs)
        assert actual_result == expected_result

    @ddt.data(
        (23, 'course-v1:org+course+basic_course', {'courses': {}}, False, True),
        (
            45,
            'course-v1:org+course+fancy_course',
            {
                'courses': {
                    'course-v1:org+course+fancy_course': True
                }
            },
            True,
            True
        ),
        (
            93,
            'course-v1:org+course+my_course',
            {
                'courses': {
                    'course-v1:org+course+my_course': False
                }
            },
            False,
            True
        ),
        (23, 'basic_course', {'courses': {}}, False, False),
        (
            45,
            'fancy_course',
            {
                'courses': {
                    'fancy_course': True
                }
            },
            True,
            False
        ),
        (93, 'my_course', {'courses': {'my_course': False}}, False, False)
    )
    @ddt.unpack
    @mock.patch('enterprise.api_client.discovery.course_discovery_api_client')
    def test_is_course_in_catalog(
            self,
            catalog_id,
            course_id,
            api_resp,
            expected,
            is_a_course_run,
            mock_discovery_client_factory
    ):
        """
        Test the API client that checks to determine if a given course ID is present
        in the given catalog.
        """
        discovery_client = mock_discovery_client_factory.return_value
        discovery_client.catalogs.return_value.contains.get.return_value = api_resp
        self.api = CourseCatalogApiClient(self.user_mock)
        assert self.api.is_course_in_catalog(catalog_id, course_id) == expected
        discovery_client.catalogs.assert_called_once_with(catalog_id)
        if is_a_course_run:
            discovery_client.catalogs.return_value.contains.get.assert_called_once_with(course_run_id=course_id)
        else:
            discovery_client.catalogs.return_value.contains.get.assert_called_once_with(course_id=course_id)

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
            {"course_runs": [{"key": "course-v1:JediAcademy+AppliedTelekinesis+T1"}]},
            "JediAcademy+AppliedTelekinesis",
            {"key": "course-v1:JediAcademy+AppliedTelekinesis+T1"}
        ),
        (
            "course-v1:JediAcademy+AppliedTelekinesis+T1",
            {},
            "JediAcademy+AppliedTelekinesis",
            None
        ),
        (
            "course-v1:JediAcademy+AppliedTelekinesis+T1",
            {"course_runs": [
                {"key": "course-v1:JediAcademy+AppliedTelekinesis+T222"},
                {"key": "course-v1:JediAcademy+AppliedTelekinesis+T1"}
            ]},
            "JediAcademy+AppliedTelekinesis",
            {"key": "course-v1:JediAcademy+AppliedTelekinesis+T1"}
        ),
        (
            "course-v1:JediAcademy+AppliedTelekinesis+T1",
            {"course_runs": []},
            "JediAcademy+AppliedTelekinesis",
            None
        )
    )
    @ddt.unpack
    def test_get_course_and_course_run(
            self,
            course_run_id,
            response_dict,
            expected_resource_id,
            expected_course_run
    ):
        """
        Verify get_course_and_course_run of CourseCatalogApiClient works as expected.
        """
        self.get_data_mock.return_value = response_dict
        expected_result = response_dict, expected_course_run

        actual_result = self.api.get_course_and_course_run(course_run_id)

        assert self.get_data_mock.call_count == 1
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
