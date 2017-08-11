# -*- coding: utf-8 -*-
"""
Client for communicating with the Enterprise API.
"""
from __future__ import absolute_import, unicode_literals

from django.conf import settings
from django.core.cache import cache

from enterprise.api_client.lms import JwtLmsApiClient
from enterprise.utils import get_cache_key, traverse_pagination


class EnterpriseApiClient(JwtLmsApiClient):
    """
    Object builds an API client to make calls to the Enterprise API.
    """

    API_BASE_URL = settings.LMS_ROOT_URL + '/enterprise/api/v1/'
    APPEND_SLASH = True

    @JwtLmsApiClient.refresh_token
    def get_enterprise_courses(self, enterprise_customer, traverse=False):
        """
        Query the Enterprise API for the courses detail of the given enterprise.

        Arguments:
            enterprise_customer (Enterprise Customer): Enterprise customer for fetching courses
            traverse (bool): Whether to traverse pagination or return paginated response

        Returns:
            dict: A dictionary containing details about the course, in an enrollment context (allowed modes, etc.)
        """
        api_resource_name = 'enterprise-customer'
        cache_key = get_cache_key(
            resource=api_resource_name,
            enterprise_uuid=enterprise_customer.uuid,
            traverse=traverse
        )
        response = cache.get(cache_key)
        if not response:
            endpoint = getattr(self.client, api_resource_name)(enterprise_customer.uuid).courses
            response = endpoint.get()
            if traverse:
                all_response_results = traverse_pagination(response, endpoint)
                response = {
                    'count': len(all_response_results),
                    'next': 'None',
                    'previous': 'None',
                    'results': all_response_results,
                }

            cache.set(cache_key, response, settings.ENTERPRISE_API_CACHE_TIMEOUT)

        return response
