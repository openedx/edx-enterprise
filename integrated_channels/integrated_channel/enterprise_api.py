"""
APIs providing support for enterprise functionality.
"""
from __future__ import absolute_import, unicode_literals

import logging

from django.conf import settings
from slumber.exceptions import HttpClientError, HttpServerError

from edx_rest_api_client.client import EdxRestApiClient
from enterprise.utils import NotConnectedToOpenEdX

try:
    from openedx.core.lib.token_utils import JwtBuilder
except ImportError:
    JwtBuilder = None


CONSENT_FAILED_PARAMETER = 'consent_failed'
ENTERPRISE_CUSTOMER_BRANDING_OVERRIDE_DETAILS = 'enterprise_customer_branding_override_details'
LOGGER = logging.getLogger("edx.enterprise_helpers")


class EnterpriseApiClient(object):
    """
    Class for producing an Enterprise service API client.
    """

    def __init__(self, user):
        """
        Initialize an Enterprise service API client.
        """
        self.user = user
        if JwtBuilder is None:
            raise NotConnectedToOpenEdX("This package must be installed in an OpenEdX environment.")

        jwt = JwtBuilder(self.user).build_token([])
        self.client = EdxRestApiClient(
            settings.ENTERPRISE_API_URL,
            jwt=jwt
        )

    def get_enterprise_courses(self, enterprise_id):
        """
        Fetch course data related to the enterprise's catalog from the Enterprise Service.
        """
        try:
            api_resource_name = 'enterprise-customer-courses'
            endpoint = getattr(self.client, api_resource_name)
            response = endpoint(enterprise_id).get()
        except (HttpClientError, HttpServerError):
            message = ("An error occurred while getting Enterprise Course data for enterprise {}".format(
                enterprise_id
            ))
            LOGGER.exception(message)
            raise

        return response['results']
