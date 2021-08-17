# -*- coding: utf-8 -*-
"""
Client for communicating with the Enterprise API.
"""

from collections import OrderedDict
from logging import getLogger

from django.conf import settings
from django.core.cache import cache

from enterprise import utils
from enterprise.api_client.lms import JwtLmsApiClient

LOGGER = getLogger(__name__)


class EnterpriseApiClient(JwtLmsApiClient):
    """
    Object builds an API client to make calls to the Enterprise API.
    """

    API_BASE_URL = settings.LMS_INTERNAL_ROOT_URL + '/enterprise/api/v1/'
    APPEND_SLASH = True

    ENTERPRISE_CUSTOMER_ENDPOINT = 'enterprise-customer'
    ENTERPRISE_CUSTOMER_CATALOGS_ENDPOINT = 'enterprise_catalogs'

    DEFAULT_VALUE_SAFEGUARD = object()

    def get_content_metadata(self, enterprise_customer, enterprise_catalogs=None):
        """
        Return all content metadata contained in the catalogs associated with the EnterpriseCustomer.

        Arguments:
            enterprise_customer (EnterpriseCustomer): The EnterpriseCustomer to return content metadata for.
            enterprise_catalogs (EnterpriseCustomerCatalog): Optional list of EnterpriseCustomerCatalog objects.

        Returns:
            list: List of dicts containing content metadata.
        """
        content_metadata = OrderedDict()
        enterprise_customer_catalogs = enterprise_catalogs or enterprise_customer.enterprise_customer_catalogs.all()
        for enterprise_customer_catalog in enterprise_customer_catalogs:
            response = self._load_data(
                self.ENTERPRISE_CUSTOMER_CATALOGS_ENDPOINT,
                resource_id=str(enterprise_customer_catalog.uuid),
                traverse_pagination=True,
                querystring={'page_size': 1000},
            )

            for item in response['results']:
                content_id = utils.get_content_metadata_item_id(item)
                content_metadata[content_id] = item

        return list(content_metadata.values())

    @JwtLmsApiClient.refresh_token
    def _load_data(
            self,
            resource,
            detail_resource=None,
            resource_id=None,
            querystring=None,
            traverse_pagination=False,
            default=DEFAULT_VALUE_SAFEGUARD,
    ):
        """
        Loads a response from a call to one of the Enterprise endpoints.

        :param resource: The endpoint resource name.
        :param detail_resource: The sub-resource to append to the path.
        :param resource_id: The resource ID for the specific detail to get from the endpoint.
        :param querystring: Optional query string parameters.
        :param traverse_pagination: Whether to traverse pagination or return paginated response.
        :param default: The default value to return in case of no response content.
        :return: Data returned by the API.
        """
        default_val = default if default != self.DEFAULT_VALUE_SAFEGUARD else {}
        querystring = querystring if querystring else {}

        cache_key = utils.get_cache_key(
            resource=resource,
            querystring=querystring,
            traverse_pagination=traverse_pagination,
            resource_id=resource_id
        )
        response = cache.get(cache_key)
        if not response:
            # Response is not cached, so make a call.
            endpoint = getattr(self.client, resource)(resource_id)
            endpoint = getattr(endpoint, detail_resource) if detail_resource else endpoint
            response = endpoint.get(**querystring)
            if traverse_pagination:
                results = utils.traverse_pagination(response, endpoint)
                response = {
                    'count': len(results),
                    'next': 'None',
                    'previous': 'None',
                    'results': results,
                }
            if response:
                # Now that we've got a response, cache it.
                cache.set(cache_key, response, settings.ENTERPRISE_API_CACHE_TIMEOUT)
        return response or default_val
