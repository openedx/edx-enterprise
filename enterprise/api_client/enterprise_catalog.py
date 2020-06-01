# -*- coding: utf-8 -*-
"""
Client for communicating with the Enterprise API.
"""

from __future__ import absolute_import, unicode_literals

import json
from collections import OrderedDict
from logging import getLogger

from requests.exceptions import ConnectionError, Timeout  # pylint: disable=redefined-builtin
from slumber.exceptions import HttpNotFoundError, SlumberBaseException

from django.conf import settings

from enterprise import utils
from enterprise.api_client.lms import JwtLmsApiClient

LOGGER = getLogger(__name__)


class EnterpriseCatalogApiClient(JwtLmsApiClient):
    """
    Object builds an API client to make calls to the Enterprise Catalog API.
    """

    API_BASE_URL = settings.ENTERPRISE_CATALOG_INTERNAL_ROOT_URL + '/api/v1/'
    ENTERPRISE_CATALOG_ENDPOINT = 'enterprise-catalogs'
    GET_CONTENT_METADATA_ENDPOINT = ENTERPRISE_CATALOG_ENDPOINT + '/{}/get_content_metadata'
    ENTERPRISE_CUSTOMER_ENDPOINT = 'enterprise-customer'
    APPEND_SLASH = True

    def __init__(self, user=None):
        user = user if user else utils.get_enterprise_worker_user()
        super(EnterpriseCatalogApiClient, self).__init__(user)

    @JwtLmsApiClient.refresh_token
    def create_enterprise_catalog(
            self,
            catalog_uuid,
            enterprise_id,
            enterprise_name,
            title,
            content_filter,
            enabled_course_modes,
            publish_audit_enrollment_urls):
        """Creates an enterprise catalog."""
        endpoint = getattr(self.client, self.ENTERPRISE_CATALOG_ENDPOINT)
        post_data = {
            'uuid': catalog_uuid,
            'title': title,
            'enterprise_customer': enterprise_id,
            'enterprise_customer_name': enterprise_name,
            'content_filter': content_filter,
            'enabled_course_modes': enabled_course_modes,
            'publish_audit_enrollment_urls': json.dumps(publish_audit_enrollment_urls),
        }
        try:
            LOGGER.info(
                'Creating Enterprise Catalog %s in the Enterprise Catalog Service with params: %s',
                catalog_uuid,
                json.dumps(post_data)
            )
            return endpoint.post(post_data)
        except (SlumberBaseException, ConnectionError, Timeout) as exc:
            LOGGER.exception(
                'Failed to create EnterpriseCustomer Catalog [%s] in enterprise-catalog due to: [%s]',
                catalog_uuid, str(exc)
            )
            return {}

    @JwtLmsApiClient.refresh_token
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
        endpoint = getattr(self.client, self.ENTERPRISE_CATALOG_ENDPOINT)(catalog_uuid)
        try:
            return endpoint.get()
        except (SlumberBaseException, ConnectionError, Timeout) as exc:
            if should_raise_exception:
                LOGGER.exception(
                    'Failed to get EnterpriseCustomer Catalog [%s] in enterprise-catalog due to: [%s]',
                    catalog_uuid, str(exc)
                )
            return {}

    @staticmethod
    def get_content_metadata_url(uuid):
        """
        Get the url for the preview information for an enterprise catalog
        """
        return EnterpriseCatalogApiClient.API_BASE_URL + \
            EnterpriseCatalogApiClient.GET_CONTENT_METADATA_ENDPOINT.format(uuid)

    @JwtLmsApiClient.refresh_token
    def update_enterprise_catalog(self, catalog_uuid, **kwargs):
        """Updates an enterprise catalog."""
        endpoint = getattr(self.client, self.ENTERPRISE_CATALOG_ENDPOINT)(catalog_uuid)
        try:
            LOGGER.info(
                'Updating Enterprise Catalog %s in the Enterprise Catalog Service with params: %s',
                catalog_uuid,
                json.dumps(kwargs)
            )
            return endpoint.put(kwargs)
        except (SlumberBaseException, ConnectionError, Timeout) as exc:
            LOGGER.exception(
                'Failed to update EnterpriseCustomer Catalog [%s] in enterprise-catalog due to: [%s]',
                catalog_uuid, str(exc)
            )
            return {}

    @JwtLmsApiClient.refresh_token
    def delete_enterprise_catalog(self, catalog_uuid):
        """Deletes an enterprise catalog."""
        endpoint = getattr(self.client, self.ENTERPRISE_CATALOG_ENDPOINT)(catalog_uuid)
        try:
            return endpoint.delete()
        except HttpNotFoundError:
            LOGGER.warning(
                'Deleted EnterpriseCustomerCatalog [%s] that was not in enterprise-catalog',
                catalog_uuid
            )
            return {}
        except (SlumberBaseException, ConnectionError, Timeout) as exc:
            LOGGER.exception(
                'Failed to delete EnterpriseCustomer Catalog [%s] in enterprise-catalog due to: [%s]',
                catalog_uuid, str(exc)
            )
            return {}

    @JwtLmsApiClient.refresh_token
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
            catalog_uuid = enterprise_customer_catalog.uuid
            endpoint = getattr(self.client, self.GET_CONTENT_METADATA_ENDPOINT.format(catalog_uuid))
            try:
                response = endpoint.get()
                for item in utils.traverse_pagination(response, endpoint):
                    content_id = utils.get_content_metadata_item_id(item)
                    content_metadata[content_id] = item
            except (SlumberBaseException, ConnectionError, Timeout) as exc:
                LOGGER.exception(
                    'Failed to get content metadata for Catalog [%s] in enterprise-catalog due to: [%s]',
                    catalog_uuid, str(exc)
                )

        return list(content_metadata.values())

    @JwtLmsApiClient.refresh_token
    def contains_content_items(self, catalog_uuid, content_ids):
        """
        Checks whether an enterprise catalog contains the given content

        The enterprise catalog endpoint does not differentiate between course_run_ids and program_uuids so they can
        be used interchangeably. The two query parameters are left in for backwards compatability with edx-enterprise.
        """
        query_params = {'course_run_ids': content_ids}
        endpoint = getattr(self.client, self.ENTERPRISE_CATALOG_ENDPOINT)(catalog_uuid)
        return endpoint.contains_content_items.get(**query_params)['contains_content_items']

    @JwtLmsApiClient.refresh_token
    def enterprise_contains_content_items(self, enterprise_uuid, content_ids):
        """
        Checks whether an enterprise customer has any catalogs that contain the provided content ids.

        The endpoint does not differentiate between course_run_ids and program_uuids so they can be used
        interchangeably. The two query parameters are left in for backwards compatability with edx-enterprise.
        """
        query_params = {'course_run_ids': content_ids}
        endpoint = getattr(self.client, self.ENTERPRISE_CUSTOMER_ENDPOINT)(enterprise_uuid)
        return endpoint.contains_content_items.get(**query_params)['contains_content_items']
