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

from enterprise.course_catalog_api import CourseCatalogApiClient
from enterprise.utils import CourseCatalogApiError, NotConnectedToOpenEdX


class TestCourseCatalogApiInitialization(unittest.TestCase):
    """
    Test initialization of CourseCatalogAPI.
    """
    @mock.patch('enterprise.course_catalog_api.CatalogIntegration')
    @mock.patch('enterprise.course_catalog_api.get_edx_api_data')
    def test_raise_error_missing_course_discovery_api(self, *args):  # pylint: disable=unused-argument
        message = 'To get a Catalog API client, this package must be installed in an Open edX environment.'
        with raises(NotConnectedToOpenEdX) as excinfo:
            CourseCatalogApiClient(mock.Mock(spec=User))
        assert message == str(excinfo.value)

    @mock.patch('enterprise.course_catalog_api.JwtBuilder')
    @mock.patch('enterprise.course_catalog_api.get_edx_api_data')
    def test_raise_error_missing_catalog_integration(self, *args):  # pylint: disable=unused-argument
        message = 'To get a CatalogIntegration object, this package must be installed in an Open edX environment.'
        with raises(NotConnectedToOpenEdX) as excinfo:
            CourseCatalogApiClient(mock.Mock(spec=User))
        assert message == str(excinfo.value)

    @mock.patch('enterprise.course_catalog_api.CatalogIntegration')
    @mock.patch('enterprise.course_catalog_api.JwtBuilder')
    def test_raise_error_missing_get_edx_api_data(self, *args):  # pylint: disable=unused-argument
        message = 'To parse a Catalog API response, this package must be installed in an Open edX environment.'
        with raises(NotConnectedToOpenEdX) as excinfo:
            CourseCatalogApiClient(mock.Mock(spec=User))
        assert message == str(excinfo.value)


@ddt.ddt
class TestCourseCatalogApi(unittest.TestCase):
    """
    Test course catalog API methods.
    """
    CATALOG_API_PATCH_PREFIX = "enterprise.course_catalog_api"

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

    def test_get_all_catalogs(self):
        response_dict = {"very": "complex", "json": {"with": " nested object"}}
        self.get_data_mock.return_value = response_dict

        actual_result = self.api.get_all_catalogs()

        assert self.get_data_mock.call_count == 1
        resource, resource_id = self._get_important_parameters(self.get_data_mock)

        assert resource == "catalogs"
        assert resource_id is None
        assert actual_result == response_dict

    def test_get_catalog_courses(self):
        expected_result = ['item1', 'item2', 'item3']
        self.get_data_mock.return_value = expected_result

        actual_result = self.api.get_catalog_courses(123)

        assert self.get_data_mock.call_count == 1
        resource, _ = self._get_important_parameters(self.get_data_mock)

        assert resource == 'catalogs/123/courses'
        assert actual_result == expected_result

    def test_get_course_details(self):
        course_key = 'edX+DemoX'
        expected_result = {"complex": "dict"}
        self.get_data_mock.return_value = expected_result

        actual_result = self.api.get_course_details(course_key)

        assert self.get_data_mock.call_count == 1
        resource, resource_id = self._get_important_parameters(self.get_data_mock)

        assert resource == 'courses'
        assert resource_id == 'edX+DemoX'
        assert actual_result == expected_result

    @ddt.data(*EMPTY_RESPONSES)
    def test_get_all_catalogs_empty_response(self, response):
        self.get_data_mock.return_value = response

        assert self.api.get_all_catalogs() == []

    def test_get_catalog(self):
        """
        Verify get_catalog of CourseCatalogApiClient works as expected.
        """
        response_dict = {"very": "complex", "json": {"with": " nested object"}}
        self.get_data_mock.return_value = response_dict

        actual_result = self.api.get_catalog(catalog_id=1)

        assert self.get_data_mock.call_count == 1
        resource, resource_id = self._get_important_parameters(self.get_data_mock)

        assert resource == "catalogs"
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

        assert self.get_data_mock.call_count == catalog_id
        resource, resource_id = self._get_important_parameters(self.get_data_mock)

        assert resource == "catalogs/{}/courses/".format(catalog_id)
        assert resource_id is None
        assert actual_result == response_dict

    def test_get_paginated_catalogs(self):
        """
        Verify get_paginated_catalogs of CourseCatalogApiClient works as expected.
        """
        response_dict = {'very': 'complex', 'json': {'with': 'nested object'}}
        self.get_data_mock.return_value = response_dict

        actual_result = self.api.get_paginated_catalogs()

        resource, resource_id = self._get_important_parameters(self.get_data_mock)

        assert resource == 'catalogs'
        assert resource_id is None
        assert actual_result == response_dict

    @ddt.data(*EMPTY_RESPONSES)
    def test_get_paginated_catalog_courses_empty_response(self, response):
        """
        Verify get_paginated_catalog_courses of CourseCatalogApiClient works as expected.
        """
        catalog_id = 1
        self.get_data_mock.return_value = response

        assert self.api.get_paginated_catalog_courses(catalog_id=catalog_id) == []

    @ddt.data(
        "course-v1:JediAcademy+AppliedTelekinesis+T1",
        "course-v1:TrantorAcademy+Psychohistory101+T1",
        "course-v1:StarfleetAcademy+WarpspeedNavigation+T2337",
        "course-v1:SinhonCompanionAcademy+Calligraphy+TermUnknown",
        "course-v1:CampArthurCurrie+HeavyWeapons+T2245_5",
    )
    def test_get_course_run(self, course_run_id):
        response_dict = {"very": "complex", "json": {"with": " nested object"}}
        self.get_data_mock.return_value = response_dict

        actual_result = self.api.get_course_run(course_run_id)

        assert self.get_data_mock.call_count == 1
        resource, resource_id = self._get_important_parameters(self.get_data_mock)

        assert resource == "course_runs"
        assert resource_id is course_run_id
        assert actual_result == response_dict

    @ddt.data(*EMPTY_RESPONSES)
    def test_get_course_run_empty_response(self, response):
        self.get_data_mock.return_value = response

        assert self.api.get_course_run("any") == {}

    @ddt.data("Apollo", "Star Wars", "mk Ultra")
    def test_get_program_by_uuid(self, program_id):
        response_dict = {"very": "complex", "json": {"with": " nested object"}}
        self.get_data_mock.return_value = response_dict

        actual_result = self.api.get_program_by_uuid(program_id)

        assert self.get_data_mock.call_count == 1
        resource, resource_id = self._get_important_parameters(self.get_data_mock)

        assert resource == "programs"
        assert resource_id is program_id
        assert actual_result == response_dict

    @ddt.data(*EMPTY_RESPONSES)
    def test_get_program_by_uuid_empty_response(self, response):
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
        self.get_data_mock.return_value = response

        actual_result = self.api.get_program_by_title(program_title)

        assert self.get_data_mock.call_count == 1
        resource, _ = self._get_important_parameters(self.get_data_mock)

        assert resource == "programs"
        assert actual_result == expected_result

    @ddt.data(*EMPTY_RESPONSES)
    def test_get_program_by_title_empty_response(self, response):
        self.get_data_mock.return_value = response

        assert self.api.get_program_by_title("any") is None

    def test_get_program_by_title_raise_multiple_match(self):
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
