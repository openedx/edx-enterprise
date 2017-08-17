# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` course catalogs api module.
"""

from __future__ import absolute_import, unicode_literals, with_statement

import unittest

import ddt
import mock
from pytest import raises

from django.contrib.auth.models import User

from enterprise.api_client.discovery import CourseCatalogApiClient
from enterprise.utils import CourseCatalogApiError, NotConnectedToOpenEdX


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
class TestCourseCatalogApi(unittest.TestCase):
    """
    Test course catalog API methods.
    """
    CATALOG_API_PATCH_PREFIX = "enterprise.api_client.discovery"

    EMPTY_RESPONSES = (None, {}, [], set(), "")

    def _make_catalog_api_location(self, catalog_api_member):
        """
        Return path for `catalog_api_member` to mock.
        """
        return "{}.{}".format(self.CATALOG_API_PATCH_PREFIX, catalog_api_member)

    def _make_patch(self, patch_location, new=None):
        """
        Patch `patch_location`, register the patch to stop at test cleanup and return mock object
        """
        patch_mock = new if new is not None else mock.Mock()
        patcher = mock.patch(patch_location, patch_mock)
        patcher.start()
        self.addCleanup(patcher.stop)
        return patch_mock

    def setUp(self):
        super(TestCourseCatalogApi, self).setUp()
        self.user_mock = mock.Mock(spec=User)
        self.get_data_mock = self._make_patch(self._make_catalog_api_location("get_edx_api_data"))
        self.catalog_api_config_mock = self._make_patch(self._make_catalog_api_location("CatalogIntegration"))
        self.jwt_builder_mock = self._make_patch(self._make_catalog_api_location("JwtBuilder"))

        self.api = CourseCatalogApiClient(self.user_mock)

    @staticmethod
    def _get_important_parameters(get_data_mock):
        """
        Return important (i.e. varying) parameters to get_edx_api_data
        """
        args, kwargs = get_data_mock.call_args

        # This test is to make sure that all calls to get_edx_api_data are made using kwargs
        # and there is no positional argument. This is required as changes in get_edx_api_data's
        # signature are breaking edx-enterprise and using kwargs would reduce that.
        assert args == ()

        return kwargs.get('resource', None), kwargs.get('resource_id', None)

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

    def test_get_paginated_search_results(self):
        """
        Verify get_paginated_search_results of CourseCatalogApiClient works as expected.
        """
        querystring = 'very'
        response_dict = {"very": "complex", "json": {"with": " nested object"}}
        self.get_data_mock.return_value = response_dict
        actual_result = self.api.get_paginated_search_results(querystring=querystring)
        assert self.get_data_mock.call_count == 1
        resource, resource_id = self._get_important_parameters(self.get_data_mock)
        assert resource == CourseCatalogApiClient.SEARCH_ALL_ENDPOINT
        assert resource_id is None
        assert actual_result == response_dict

    @ddt.data(*EMPTY_RESPONSES)
    def test_get_paginated_search_results_empty_response(self, response):
        """
        Verify get_paginated_catalog_courses of CourseCatalogApiClient works as expected for empty responses.
        """
        self.get_data_mock.return_value = response
        assert self.api.get_paginated_search_results(querystring='querystring') == []

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
        assert self.api.get_course_details(course_key='edX+DemoX') == {}

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

    @mock.patch('enterprise.api_client.discovery.course_discovery_api_client')
    @ddt.data(
        (23, 'course-id', {'courses': {}}, False),
        (45, 'fancy-course', {'courses': {'fancy-course': True}}, True),
        (93, 'my-course', {'courses': {'my-course': False}}, False)
    )
    @ddt.unpack
    def test_is_course_in_catalog(self, catalog_id, course_id, api_resp, expected, mock_discovery_client_factory):
        """
        Test the API client that checks to determine if a given course ID is present
        in the given catalog.
        """
        discovery_client = mock_discovery_client_factory.return_value
        discovery_client.catalogs.return_value.contains.get.return_value = api_resp
        self.api = CourseCatalogApiClient(self.user_mock)
        assert self.api.is_course_in_catalog(catalog_id, course_id) == expected
        discovery_client.catalogs.assert_called_once_with(catalog_id)
        discovery_client.catalogs.return_value.contains.get.assert_called_once_with(course_run_id=course_id)
