"""
Client for communicating with the Enterprise API.
"""

import json
from collections import OrderedDict
from logging import getLogger
from urllib.parse import urljoin

from requests.exceptions import ConnectionError, RequestException, Timeout  # pylint: disable=redefined-builtin

from django.conf import settings

from enterprise import utils
from enterprise.api_client.client import NoAuthAPIClient, UserAPIClient

LOGGER = getLogger(__name__)


class EnterpriseCatalogApiClient(UserAPIClient):
    """
    The API client to make calls to the Enterprise Catalog API.
    """

    API_BASE_URL = urljoin(f"{settings.ENTERPRISE_CATALOG_INTERNAL_ROOT_URL}/", "api/v1/")
    ENTERPRISE_CATALOG_ENDPOINT = 'enterprise-catalogs'
    GET_CONTENT_METADATA_ENDPOINT = ENTERPRISE_CATALOG_ENDPOINT + '/{}/get_content_metadata'
    REFRESH_CATALOG_ENDPOINT = ENTERPRISE_CATALOG_ENDPOINT + '/{}/refresh_metadata'
    CATALOG_DIFF_ENDPOINT = ENTERPRISE_CATALOG_ENDPOINT + '/{}/generate_diff'
    ENTERPRISE_CUSTOMER_ENDPOINT = 'enterprise-customer'
    APPEND_SLASH = True
    GET_CONTENT_METADATA_PAGE_SIZE = getattr(settings, 'ENTERPRISE_CATALOG_GET_CONTENT_METADATA_PAGE_SIZE', 50)

    def __init__(self, user=None):
        user = user if user else utils.get_enterprise_worker_user()
        super().__init__(user)

    @UserAPIClient.refresh_token
    def create_enterprise_catalog(
            self,
            catalog_uuid,
            enterprise_id,
            enterprise_name,
            title,
            content_filter,
            enabled_course_modes,
            publish_audit_enrollment_urls,
            catalog_query_uuid,
            query_title=None,
            include_exec_ed_2u_courses=False,
    ):
        """
        Creates an enterprise catalog.
        """
        api_url = self.get_api_url(f"{self.ENTERPRISE_CATALOG_ENDPOINT}")
        post_data = {
            'uuid': catalog_uuid,
            'title': title,
            'enterprise_customer': enterprise_id,
            'enterprise_customer_name': enterprise_name,
            'content_filter': content_filter,
            'enabled_course_modes': enabled_course_modes,
            'publish_audit_enrollment_urls': json.dumps(publish_audit_enrollment_urls),
            'catalog_query_uuid': catalog_query_uuid,
            'query_title': query_title,
            'include_exec_ed_2u_courses': include_exec_ed_2u_courses,
        }
        try:
            LOGGER.info(
                'Creating Enterprise Catalog %s in the Enterprise Catalog Service with params: %s',
                catalog_uuid,
                json.dumps(post_data)
            )
            response = self.client.post(api_url, json=post_data)
            response.raise_for_status()
            return response.json()
        except (RequestException, ConnectionError, Timeout) as exc:
            LOGGER.exception(
                'Failed to create EnterpriseCustomer Catalog [%s] in enterprise-catalog due to: [%s]',
                catalog_uuid, str(exc)
            )
            return {}

    @UserAPIClient.refresh_token
    def get_enterprise_catalog(self, catalog_uuid, should_raise_exception=True):
        """
        Gets an enterprise catalog.

        Arguments:
            catalog_uuid (uuid): The uuid of an EnterpriseCatalog instance
            should_raise_exception (bool): Whether an exception should be logged if
                a catalog does not yet exist in enterprise-catalog. Defaults to True.

        Returns:
            dict: a dictionary representing an enterprise catalog
        """
        api_url = self.get_api_url(f"{self.ENTERPRISE_CATALOG_ENDPOINT}/{catalog_uuid}")
        try:
            response = self.client.get(api_url)
            response.raise_for_status()
            return response.json()
        except (RequestException, ConnectionError, Timeout) as exc:
            if should_raise_exception:
                LOGGER.exception(
                    'Failed to get EnterpriseCustomer Catalog [%s] in enterprise-catalog due to: [%s]',
                    catalog_uuid, str(exc)
                )
            return {}

    @UserAPIClient.refresh_token
    def get_catalog_diff(self, enterprise_customer_catalog, content_keys, should_raise_exception=True):
        """
        Gets the representational difference between a list of course keys and the current state of content under an
        enterprise catalog. This difference is returned as three buckets of data: `items_not_found`,
        `items_not_included` and `items_found`.

        Arguments:
            enterprise_customer_catalog (EnterpriseCustomerCatalog): The catalog object whose content is being diffed.
            content_keys (list): List of string content keys
            should_raise_exception (Bool): Optional param for whether or not api response exceptions should be raised.

        Returns:
            items_to_create (list): dictionaries of content_keys to create
            items_to_delete (list): dictionaries of content_keys to delete
            items_found (list): dictionaries of content_keys and date_updated datetimes of content to update
        """
        catalog_uuid = enterprise_customer_catalog.uuid
        api_url = self.get_api_url(self.CATALOG_DIFF_ENDPOINT.format(catalog_uuid))
        body = {'content_keys': content_keys}

        items_to_delete = []
        items_to_create = []
        items_found = []
        try:
            response = self.client.post(api_url, json=body)
            response.raise_for_status()
            results = response.json()
            items_to_delete = results.get('items_not_found')
            items_to_create = results.get('items_not_included')
            items_found = results.get('items_found')

        except (RequestException, ConnectionError, Timeout) as exc:
            LOGGER.exception(
                'Failed to get EnterpriseCustomer Catalog [%s] in enterprise-catalog due to: [%s]',
                catalog_uuid, str(exc)
            )
            if should_raise_exception:
                raise

        return items_to_create, items_to_delete, items_found

    @staticmethod
    def get_content_metadata_url(uuid):
        """
        Get the url for the preview information for an enterprise catalog
        """
        return EnterpriseCatalogApiClient.API_BASE_URL + \
            EnterpriseCatalogApiClient.GET_CONTENT_METADATA_ENDPOINT.format(uuid)

    @UserAPIClient.refresh_token
    def update_enterprise_catalog(self, catalog_uuid, **kwargs):
        """
        Updates an enterprise catalog.
        """
        api_url = self.get_api_url(f"{self.ENTERPRISE_CATALOG_ENDPOINT}/{catalog_uuid}")
        try:
            LOGGER.info(
                'Updating Enterprise Catalog %s in the Enterprise Catalog Service with params: %s',
                catalog_uuid,
                json.dumps(kwargs)
            )
            response = self.client.put(api_url, json=kwargs)
            response.raise_for_status()
            return response.json()
        except (RequestException, ConnectionError, Timeout) as exc:
            LOGGER.exception(
                'Failed to update EnterpriseCustomer Catalog [%s] in enterprise-catalog due to: [%s]',
                catalog_uuid, str(exc)
            )
            return {}

    @UserAPIClient.refresh_token
    def delete_enterprise_catalog(self, catalog_uuid):
        """
        Deletes an enterprise catalog.
        """
        api_url = self.get_api_url(f"{self.ENTERPRISE_CATALOG_ENDPOINT}/{catalog_uuid}")
        try:
            response = self.client.delete(api_url)
            response.raise_for_status()
            return 200 <= response.status_code <= 299
        except (RequestException, ConnectionError, Timeout) as exc:
            if exc.response is not None and exc.response.status_code == 404:
                LOGGER.warning(
                    'Deleted EnterpriseCustomerCatalog [%s] that was not in enterprise-catalog',
                    catalog_uuid
                )
            else:
                LOGGER.exception(
                    'Failed to delete EnterpriseCustomer Catalog [%s] in enterprise-catalog due to: [%s]',
                    catalog_uuid, str(exc)
                )
            return {}

    def traverse_get_content_metadata(self, api_url, query, catalog_uuid):
        """
        Helper method to traverse over a paginated response from the enterprise-catalog service's `get_content_metadata`
        endpoint.
        """
        content_metadata = OrderedDict()
        try:
            response = self.client.get(api_url, params=query)
            response.raise_for_status()
            for item in utils.traverse_pagination(response.json(), self.client, api_url):
                content_id = utils.get_content_metadata_item_id(item)
                content_metadata[content_id] = item
        except (RequestException, ConnectionError, Timeout):
            LOGGER.exception('Failed to get content metadata for Catalog %s in enterprise-catalog', catalog_uuid)
            raise

        return content_metadata

    @UserAPIClient.refresh_token
    def get_content_metadata(self, enterprise_customer, enterprise_catalogs=None, content_keys_filter=None):
        """
        Return all content metadata contained in the catalogs associated with the EnterpriseCustomer.

        Arguments:
            enterprise_customer (EnterpriseCustomer): The EnterpriseCustomer to return content metadata for.
            enterprise_catalogs (EnterpriseCustomerCatalog): Optional list of EnterpriseCustomerCatalog objects.
            content_keys_filter (List): List of content keys to filter by in the content metadata endpoint

        Returns:
            list: List of dicts containing content metadata.
        """
        content_metadata = OrderedDict()
        enterprise_customer_catalogs = enterprise_catalogs or enterprise_customer.enterprise_customer_catalogs.all()
        for enterprise_customer_catalog in enterprise_customer_catalogs:
            catalog_uuid = enterprise_customer_catalog.uuid
            api_url = self.get_api_url(self.GET_CONTENT_METADATA_ENDPOINT.format(catalog_uuid))
            # If content keys filter exists then chunk up the keys into reasonable request sizes
            if content_keys_filter:
                chunked_keys_filter = utils.batch(
                    content_keys_filter,
                    self.GET_CONTENT_METADATA_PAGE_SIZE
                )
                # A chunk can be larger than the page size so traverse pagination for each individual chunk
                for chunk in chunked_keys_filter:
                    query = {'page_size': self.GET_CONTENT_METADATA_PAGE_SIZE, 'content_keys': chunk}
                    content_metadata.update(self.traverse_get_content_metadata(api_url, query, catalog_uuid))
            # Traverse pagination for the get all content response without filters
            else:
                query = {'page_size': self.GET_CONTENT_METADATA_PAGE_SIZE}
                content_metadata.update(self.traverse_get_content_metadata(api_url, query, catalog_uuid))

        return list(content_metadata.values())

    @UserAPIClient.refresh_token
    def refresh_catalogs(self, enterprise_catalogs):
        """
        Kicks off async tasks to refresh catalogs so recent changes will populate to production without needing to wait
        for the daily jobs to run

        Arguments:
            enterprise_catalogs (EnterpriseCustomerCatalog): List of EnterpriseCustomerCatalog objects to refresh

        Returns:
            Dict: Dict of async task ids for each catalog id
        """
        refreshed_catalogs = {}
        failed_to_refresh_catalogs = []
        for enterprise_customer_catalog in enterprise_catalogs:
            catalog_uuid = enterprise_customer_catalog.uuid
            api_url = self.get_api_url(self.REFRESH_CATALOG_ENDPOINT.format(catalog_uuid))
            try:
                response = self.client.post(api_url)
                response.raise_for_status()
                refreshed_catalogs[catalog_uuid] = response.json()['async_task_id']
            except (RequestException, ConnectionError, Timeout):
                LOGGER.exception(
                    'Failed to refresh catalog data for catalog [%s] in enterprise-catalog.', catalog_uuid
                )
                failed_to_refresh_catalogs.append(catalog_uuid)

        return refreshed_catalogs, failed_to_refresh_catalogs

    @UserAPIClient.refresh_token
    def contains_content_items(self, catalog_uuid, content_ids):
        """
        Checks whether an enterprise catalog contains the given content.

        The enterprise catalog endpoint does not differentiate between course_run_ids and program_uuids so they can
        be used interchangeably. The two query parameters are left in for backwards compatability with edx-enterprise.
        """
        query_params = {'course_run_ids': content_ids}
        api_url = self.get_api_url(f"{self.ENTERPRISE_CATALOG_ENDPOINT}/{catalog_uuid}/contains_content_items")
        response = self.client.get(api_url, params=query_params)
        response.raise_for_status()
        return response.json()['contains_content_items']

    @UserAPIClient.refresh_token
    def enterprise_contains_content_items(self, enterprise_uuid, content_ids):
        """
        Checks whether an enterprise customer has any catalogs that contain the provided content ids.

        The endpoint does not differentiate between course_run_ids and program_uuids so they can be used
        interchangeably. The two query parameters are left in for backwards compatability with edx-enterprise.
        """
        query_params = {'course_run_ids': content_ids}
        api_url = self.get_api_url(f"{self.ENTERPRISE_CUSTOMER_ENDPOINT}/{enterprise_uuid}/contains_content_items")
        response = self.client.get(api_url, params=query_params)
        response.raise_for_status()
        return response.json()['contains_content_items']


class NoAuthEnterpriseCatalogClient(NoAuthAPIClient):
    """
    The enterprise catalog API client to make calls to the discovery service.
    """

    API_BASE_URL = settings.ENTERPRISE_CATALOG_INTERNAL_ROOT_URL
    APPEND_SLASH = False
