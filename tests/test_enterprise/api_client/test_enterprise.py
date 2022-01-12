"""
Test the Enterprise API client functionality.
"""

import unittest
from unittest import mock

import ddt
import responses
from pytest import mark

from django.conf import settings
from django.core.cache import cache

from enterprise.api_client import enterprise as enterprise_api
from enterprise.models import EnterpriseCustomerCatalog
from enterprise.utils import get_cache_key, get_content_metadata_item_id
from test_utils.factories import EnterpriseCustomerCatalogFactory, EnterpriseCustomerFactory, UserFactory
from test_utils.fake_catalog_api import CourseDiscoveryApiTestMixin
from test_utils.fake_enterprise_api import EnterpriseMockMixin


@ddt.ddt
@mark.django_db
class TestEnterpriseApiClient(unittest.TestCase, EnterpriseMockMixin, CourseDiscoveryApiTestMixin):
    """
    Test enterprise API client methods.
    """

    def setUp(self):
        """
        DRY method for TestEnterpriseApiClient.
        """
        self.enterprise_customer = EnterpriseCustomerFactory(
            name='Veridian Dynamics',
        )
        super().setUp()
        self.catalog_api_config_mock = self._make_patch(self._make_catalog_api_location("CatalogIntegration"))
        self.user = UserFactory(is_staff=True)

    def tearDown(self):
        """
        Clear any existing cache.
        """
        cache.clear()
        super().tearDown()

    def _assert_enterprise_courses_api_response(self, content_ids, content_metadata, expected_count):
        """
        DRY method to verify the enterprise courses api response.
        """
        assert len(content_ids) == len(content_metadata)
        assert expected_count == len(content_metadata)
        for item in content_metadata:
            assert get_content_metadata_item_id(item) in content_ids

    def _assert_num_requests(self, expected_count):
        """
        DRY helper for verifying request counts.
        """
        assert len(responses.calls) == expected_count

    @responses.activate
    @mock.patch('enterprise.api_client.lms.JwtBuilder', mock.Mock())
    @mock.patch('enterprise.api_client.discovery.get_edx_api_data', mock.Mock())
    @mock.patch('enterprise.api_client.discovery.JwtBuilder', mock.Mock())
    def test_no_response_doesnt_get_cached(self):
        """
        Response doesn't get cached when empty.
        """
        EnterpriseCustomerCatalogFactory(
            enterprise_customer=self.enterprise_customer,
        )
        enterprise_catalog_uuid = str(self.enterprise_customer.enterprise_customer_catalogs.first().uuid)

        api_resource_name = 'enterprise_catalogs'
        cache_key = get_cache_key(
            resource=api_resource_name,
            querystring={},
            traverse_pagination=False,
            resource_id=enterprise_catalog_uuid,
        )

        cached_enterprise_api_response = cache.get(cache_key)
        assert cached_enterprise_api_response is None

        self.mock_empty_response('enterprise-catalogs-detail', enterprise_catalog_uuid)
        client = enterprise_api.EnterpriseApiClient(self.user)
        response = client._load_data(  # pylint: disable=protected-access
            resource=api_resource_name,
            resource_id=enterprise_catalog_uuid,
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
    def test_get_content_metadata_with_enterprise_catalogs(self):
        """
        Verify that the client method `get_content_metadata` works as expected.
        """
        EnterpriseCustomerCatalogFactory(
            enterprise_customer=self.enterprise_customer,
        )
        uuid = str(self.enterprise_customer.uuid)

        enterprise_catalog_uuid = str(self.enterprise_customer.enterprise_customer_catalogs.first().uuid)
        self.mock_enterprise_customer_catalogs(enterprise_catalog_uuid)

        api_resource_name = 'enterprise-customer'
        cache_key = get_cache_key(
            resource=api_resource_name,
            querystring={},
            resource_id=uuid,
            traverse_pagination=False,
        )
        cached_enterprise_api_response = cache.get(cache_key)
        self.assertIsNone(cached_enterprise_api_response)

        # Verify that by default enterprise client fetches all the course runs associated with the catalog.
        client = enterprise_api.EnterpriseApiClient(self.user)
        course_runs = client.get_content_metadata(self.enterprise_customer)
        assert len(course_runs) == 3

    @responses.activate
    @mock.patch('enterprise.api_client.lms.JwtBuilder', mock.Mock())
    def test_get_content_metadata_with_enterprise_catalog_set_to_none(self):
        """
        Verify that the client method `get_content_metadata` returns courses from
        associated EnterpriseCustomerCatalog objects only if EnterpriseCustomer.catalog is set to None.
        """
        EnterpriseCustomerCatalogFactory(
            enterprise_customer=self.enterprise_customer,
        )

        enterprise_catalog_uuid = str(self.enterprise_customer.enterprise_customer_catalogs.first().uuid)
        self.mock_enterprise_customer_catalogs(enterprise_catalog_uuid)

        api_resource_name = 'enterprise-customer'
        cache_key = get_cache_key(
            resource=api_resource_name,
            querystring={},
            resource_id=str(self.enterprise_customer.uuid),
            traverse_pagination=False,
        )
        cached_enterprise_api_response = cache.get(cache_key)
        self.assertIsNone(cached_enterprise_api_response)

        # Verify that by default enterprise client fetches all the course runs associated with the enterprise catalog.
        client = enterprise_api.EnterpriseApiClient(self.user)
        course_runs = client.get_content_metadata(self.enterprise_customer)
        assert len(course_runs) == 3

    @mock.patch('enterprise.api_client.lms.JwtBuilder', mock.Mock())
    @mock.patch('enterprise.api_client.enterprise.EnterpriseApiClient._load_data')
    def test_get_content_metadata_with_catalogs_to_transmit(self, mock_load_data):
        """
        Verify that the client method `get_content_metadata` returns courses
        from catalogs passed in 'catalogs_to_transmit' parameter.
        """
        enterprise_catalog = EnterpriseCustomerCatalogFactory(enterprise_customer=self.enterprise_customer)
        client = enterprise_api.EnterpriseApiClient(self.user)
        # get_content_metadata will transmit the 'enterprise_customer' catalogs
        client.get_content_metadata(self.enterprise_customer)
        assert mock_load_data.called
        assert mock_load_data.call_args[1]['resource_id'] == str(enterprise_catalog.uuid)

        other_catalog = EnterpriseCustomerCatalogFactory()
        # get_content_metadata will transmit the catalogs which are being passed in 'catalogs_to_transmit'
        client.get_content_metadata(
            self.enterprise_customer,
            enterprise_catalogs=EnterpriseCustomerCatalog.objects.filter(uuid=other_catalog.uuid)
        )
        assert mock_load_data.called
        assert mock_load_data.call_args[1]['resource_id'] == str(other_catalog.uuid)
