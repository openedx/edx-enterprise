"""
API client for calls to the license-manager service.
"""
import logging

import requests
from django.conf import settings
from enterprise.api_client.client import BackendServiceAPIClient
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

class LicenseManagerApiClient(BackendServiceAPIClient):
    """
    API client for calls to the license-manager service.
    """
    LICENSE_MANAGER_BASE_URL = urljoin(f"{settings.LICENSE_MANAGER_URL}/", "api/v1/")
    SUBSCRIPTIONS_ENDPOINT = LICENSE_MANAGER_BASE_URL + 'subscriptions/?enterprise_customer_uuid='

    def get_customer_subscriptions(self, customer_uuid):
        """
        Call license-manager API for data about a SubscriptionPlan.

        Arguments:
            subscription_uuid (UUID): UUID of the SubscriptionPlan in license-manager
        Returns:
            dict: Dictionary representation of json returned from API
        """
        try:
            endpoint = self.SUBSCRIPTIONS_ENDPOINT + str(customer_uuid)
            response = self.client.get(endpoint)
            return response.json().get('results')
        except requests.exceptions.HTTPError as exc:
            logger.exception(exc)
            raise