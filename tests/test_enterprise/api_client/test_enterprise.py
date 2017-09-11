"""
Test the Enterprise API client functionality.
"""
from __future__ import absolute_import, unicode_literals, with_statement

import unittest

import mock
import responses
from pytest import mark

from django.conf import settings
from django.core.cache import cache

from enterprise.api_client import enterprise as enterprise_api
from enterprise.utils import get_cache_key
from test_utils.factories import EnterpriseCustomerFactory, UserFactory
from test_utils.fake_enterprise_api import EnterpriseMockMixin


@mark.django_db
class TestEnterpriseApiClient(unittest.TestCase, EnterpriseMockMixin):
    """
    Test enterprise API client methods.
    """

    def setUp(self):
        """
        DRY method for TestEnterpriseApiClient.
        """
        self.enterprise_customer = EnterpriseCustomerFactory(
            catalog=1,
            name='Veridian Dynamics',
        )
        super(TestEnterpriseApiClient, self).setUp()
        self.user = UserFactory(is_staff=True)

    def tearDown(self):
        """
        Clear any existing cache.
        """
        cache.clear()
        super(TestEnterpriseApiClient, self).tearDown()

    def _assert_enterprise_courses_api_response(self, course_run_ids, api_response, expected_courses_count):
        """
        DRY method to verify the enterprise courses api response.
        """
        assert len(course_run_ids) == api_response.get('count')
        assert expected_courses_count == len(api_response.get('results'))
        for course_data in api_response.get('results'):
            assert course_data['course_runs'][0]['key'] in course_run_ids

    def _assert_num_requests(self, expected_count):
        """
        DRY helper for verifying request counts.
        """
        assert len(responses.calls) == expected_count

    @responses.activate
    @mock.patch('enterprise.api_client.lms.JwtBuilder', mock.Mock())
    def test_no_response_doesnt_get_cached(self):
        """
        Response doesn't get cached when empty.
        """
        uuid = str(self.enterprise_customer.uuid)
        api_resource_name = 'enterprise-customer'
        cache_key = get_cache_key(
            resource=api_resource_name,
            querystring={},
            traverse_pagination=False,
            resource_id=uuid,
        )

        cached_enterprise_api_response = cache.get(cache_key)
        assert cached_enterprise_api_response is None

        self.mock_empty_response('enterprise-customer-courses', uuid)
        client = enterprise_api.EnterpriseApiClient(self.user)
        response = client._load_data(  # pylint: disable=protected-access
            resource=api_resource_name,
            detail_resource='courses',
            resource_id=uuid,
        )
        assert not response

        # The empty response is not cached.
        cached_api_response = cache.get(cache_key)
        assert not cached_api_response

    @mock.patch('enterprise.api_client.lms.JwtBuilder', mock.Mock())
    def test_skip_request_if_response_cached(self):
        """
        We skip the request portion of the API's logic if the response is already cached.
        """
        cache_key = get_cache_key(
            resource='resource',
            querystring={},
            traverse_pagination=False,
            resource_id=None,
        )
        cache_value = {'fake': 'response'}
        cache.set(cache_key, cache_value, settings.ENTERPRISE_API_CACHE_TIMEOUT)
        client = enterprise_api.EnterpriseApiClient(self.user)
        response = client._load_data('resource')  # pylint: disable=protected-access
        assert response == cache_value

    @responses.activate
    @mock.patch('enterprise.api_client.lms.JwtBuilder', mock.Mock())
    def test_get_enterprise_courses(self):
        """
        Verify that the client method `get_all_catalogs` works as expected.
        """
        uuid = str(self.enterprise_customer.uuid)
        course_run_ids = ['course-v1:edX+DemoX+Demo_Course_1', 'course-v1:edX+DemoX+Demo_Course_2']
        self.mock_ent_courses_api_with_pagination(
            enterprise_uuid=uuid,
            course_run_ids=course_run_ids
        )

        api_resource_name = 'enterprise-customer'
        cache_key = get_cache_key(
            resource=api_resource_name,
            querystring={},
            resource_id=uuid,
            traverse_pagination=False,
        )
        cached_enterprise_api_response = cache.get(cache_key)
        self.assertIsNone(cached_enterprise_api_response)

        # Verify that by default enterprise client only fetches first paginated
        # response as the option `traverse_pagination` is False.
        client = enterprise_api.EnterpriseApiClient(self.user)
        api_response = client.get_enterprise_courses(self.enterprise_customer)
        self._assert_enterprise_courses_api_response(course_run_ids, api_response, expected_courses_count=1)
        # Verify the enterprise API was hit once
        self._assert_num_requests(1)

    @responses.activate
    @mock.patch('enterprise.api_client.lms.JwtBuilder', mock.Mock())
    def test_get_enterprise_courses_with_traverse_pagination(self):
        """
        Verify that the client method `get_all_catalogs` fetches all courses.

        The client method `get_all_catalogs` fetches all enterprise courses
        from paginated API when the option `traverse_pagination` is True.
        """
        uuid = str(self.enterprise_customer.uuid)
        course_run_ids = ['course-v1:edX+DemoX+Demo_Course_1', 'course-v1:edX+DemoX+Demo_Course_2']
        self.mock_ent_courses_api_with_pagination(
            enterprise_uuid=uuid,
            course_run_ids=course_run_ids
        )

        api_resource_name = 'enterprise-customer'
        traverse_pagination = True
        cache_key = get_cache_key(
            resource=api_resource_name,
            querystring={},
            resource_id=uuid,
            traverse_pagination=traverse_pagination,
        )
        cached_enterprise_api_response = cache.get(cache_key)
        self.assertIsNone(cached_enterprise_api_response)

        # Verify that by default enterprise client only fetches first paginated
        # response as the option `traverse_pagination` is False.
        client = enterprise_api.EnterpriseApiClient(self.user)
        api_response = client.get_enterprise_courses(self.enterprise_customer, traverse_pagination=traverse_pagination)
        self._assert_enterprise_courses_api_response(
            course_run_ids, api_response, expected_courses_count=len(course_run_ids)
        )
        # Verify the enterprise API was called multiple time for each paginated view
        self._assert_num_requests(len(course_run_ids))
