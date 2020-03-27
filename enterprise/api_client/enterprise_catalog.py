# -*- coding: utf-8 -*-
"""
Client for communicating with the Enterprise API.
"""

from __future__ import absolute_import, unicode_literals

import json
from logging import getLogger

from requests.exceptions import ConnectionError, Timeout  # pylint: disable=redefined-builtin
from slumber.exceptions import HttpNotFoundError, SlumberBaseException

from django.conf import settings

from enterprise.api_client.lms import JwtLmsApiClient

LOGGER = getLogger(__name__)


class EnterpriseCatalogApiClient(JwtLmsApiClient):
    """
    Object builds an API client to make calls to the Enterprise Catalog API.
    """

    API_BASE_URL = settings.ENTERPRISE_CATALOG_INTERNAL_ROOT_URL + '/api/v1/'
    ENTERPRISE_CATALOG_ENDPOINT = 'enterprise-catalogs'
    APPEND_SLASH = True

    @JwtLmsApiClient.refresh_token
    def create_enterprise_catalog(
            self,
            catalog_uuid,
            enterprise_id,
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
            'content_filter': content_filter,
            'enabled_course_modes': enabled_course_modes,
            'publish_audit_enrollment_urls': json.dumps(publish_audit_enrollment_urls),
        }
        try:
            return endpoint.post(post_data)
        except (SlumberBaseException, ConnectionError, Timeout) as exc:
            LOGGER.exception(
                'Failed to create EnterpriseCustomer Catalog [%s] in enterprise-catalog due to: [%s]',
                catalog_uuid, str(exc)
            )
            return {}

    @JwtLmsApiClient.refresh_token
    def get_enterprise_catalog(self, catalog_uuid):
        """Gets an enterprise catalog."""
        endpoint = getattr(self.client, self.ENTERPRISE_CATALOG_ENDPOINT)(catalog_uuid)
        try:
            return endpoint.get()
        except (SlumberBaseException, ConnectionError, Timeout) as exc:
            LOGGER.exception(
                'Failed to get EnterpriseCustomer Catalog [%s] in enterprise-catalog due to: [%s]',
                catalog_uuid, str(exc)
            )
            return {}

    @JwtLmsApiClient.refresh_token
    def update_enterprise_catalog(self, catalog_uuid, **kwargs):
        """Updates an enterprise catalog."""
        endpoint = getattr(self.client, self.ENTERPRISE_CATALOG_ENDPOINT)(catalog_uuid)
        try:
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
