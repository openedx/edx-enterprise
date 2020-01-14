# -*- coding: utf-8 -*-
"""
Client for communicating with the Enterprise API.
"""

from __future__ import absolute_import, unicode_literals

import json
from logging import getLogger

from django.conf import settings

from enterprise.api_client.lms import JwtLmsApiClient

LOGGER = getLogger(__name__)


class EnterpriseCatalogApiClient(JwtLmsApiClient):
    """
    Object builds an API client to make calls to the Enterprise Catalog API.
    """

    API_BASE_URL = settings.ENTERPRISE_CATALOG_INTERNAL_ROOT_URL + '/api/v1/'
    ENTERPRISE_CATALOG_ENDPOINT = 'enterprise-catalog'
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
        return endpoint.post(post_data)

    @JwtLmsApiClient.refresh_token
    def get_enterprise_catalog(self, catalog_uuid):
        """Gets an enterprise catalog."""
        endpoint = getattr(self.client, self.ENTERPRISE_CATALOG_ENDPOINT)(catalog_uuid)
        return endpoint.get()

    @JwtLmsApiClient.refresh_token
    def update_enterprise_catalog(self, catalog_uuid, **kwargs):
        """Updates an enterprise catalog."""
        endpoint = getattr(self.client, self.ENTERPRISE_CATALOG_ENDPOINT)(catalog_uuid)
        return endpoint.put(kwargs)

    @JwtLmsApiClient.refresh_token
    def delete_enterprise_catalog(self, catalog_uuid):
        """Deletes an enterprise catalog."""
        endpoint = getattr(self.client, self.ENTERPRISE_CATALOG_ENDPOINT)(catalog_uuid)
        return endpoint.delete()
