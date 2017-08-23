"""
Test the Enterprise API client functionality.
"""
from __future__ import absolute_import, unicode_literals, with_statement

import unittest

import mock
import responses
from pytest import mark

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
        cache_key = get_cache_key(resource=api_resource_name, enterprise_uuid=uuid, traverse=False)
        cached_enterprise_api_response = cache.get(cache_key)
        self.assertIsNone(cached_enterprise_api_response)

        # Verify that by default enterprise client only fetches first paginated
        # response as the option `traverse` is False.
        client = enterprise_api.EnterpriseApiClient(self.user)
        api_response = client.get_enterprise_courses(self.enterprise_customer)
        self._assert_enterprise_courses_api_response(course_run_ids, api_response, expected_courses_count=1)
        # Verify the enterprise API was hit once
        self._assert_num_requests(1)

        # Now fetch the enterprise courses data again and verify that there was
        # no actual call to Enterprise API, as the data will be fetched from
        # the cache
        client.get_enterprise_courses(self.enterprise_customer)
        self._assert_num_requests(1)
        cached_api_response = cache.get(cache_key)
        assert cached_api_response == api_response

    @responses.activate
    @mock.patch('enterprise.api_client.lms.JwtBuilder', mock.Mock())
    def test_get_enterprise_courses_with_traverse(self):
        """
        Verify that the client method `get_all_catalogs` fetches all courses.

        The client method `get_all_catalogs` fetches all enterprise courses
        from paginated API when the option `traverse` is True.
        """
        uuid = str(self.enterprise_customer.uuid)
        course_run_ids = ['course-v1:edX+DemoX+Demo_Course_1', 'course-v1:edX+DemoX+Demo_Course_2']
        self.mock_ent_courses_api_with_pagination(
            enterprise_uuid=uuid,
            course_run_ids=course_run_ids
        )

        api_resource_name = 'enterprise-customer'
        traverse_pagination = True
        cache_key = get_cache_key(resource=api_resource_name, enterprise_uuid=uuid, traverse=traverse_pagination)
        cached_enterprise_api_response = cache.get(cache_key)
        self.assertIsNone(cached_enterprise_api_response)

        # Verify that by default enterprise client only fetches first paginated
        # response as the option `traverse` is False.
        client = enterprise_api.EnterpriseApiClient(self.user)
        api_response = client.get_enterprise_courses(self.enterprise_customer, traverse=traverse_pagination)
        self._assert_enterprise_courses_api_response(
            course_run_ids, api_response, expected_courses_count=len(course_run_ids)
        )
        # Verify the enterprise API was called multiple time for each paginated view
        self._assert_num_requests(len(course_run_ids))

        # Now fetch the enterprise courses data again and verify that there was
        # no actual call to Enterprise API, as the data will be fetched from
        # the cache
        client.get_enterprise_courses(self.enterprise_customer, traverse=traverse_pagination)
        self._assert_num_requests(len(course_run_ids))
        cached_api_response = cache.get(cache_key)
        assert cached_api_response == api_response
