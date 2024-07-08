"""
API client for calls to the license-manager service.
"""
import logging

import requests
from django.conf import settings
from enterprise.api_client.client import BackendServiceAPIClient, NoAuthAPIClient, UserAPIClient


logger = logging.getLogger(__name__)

class LicenseManagerApiClient(BackendServiceAPIClient):
    """
    API client for calls to the license-manager service.
    """
    # def __init__(self, user):
    #     """
    #     Create an E-Commerce API client, authenticated with the API token.

    #     This method retrieves an authenticated API client that can be used
    #     to access the ecommerce API. It raises an exception to be caught at
    #     a higher level if the package doesn't have OpenEdX resources available.
    #     """
    #     if get_ecommerce_api_client is None or configuration_helpers is None:
    #         raise NotConnectedToOpenEdX(
    #             _('To get a ecommerce_api_client, this package must be '
    #               'installed in an Open edX environment.')
    #         )

    #     self.user = user
    #     self.client = get_ecommerce_api_client(user)
    #     self.API_BASE_URL = configuration_helpers.get_value(  # pylint: disable=invalid-name
    #         'ECOMMERCE_API_URL', settings.ECOMMERCE_API_URL
    #     )

    api_base_url = 'http://license-manager.app:18170' + '/api/v1/'
    subscriptions_endpoint = api_base_url + 'subscriptions/?enterprise_customer_uuid='

    def get_customer_subscriptions(self, customer_uuid):
        """
        Call license-manager API for data about a SubscriptionPlan.

        Arguments:
            subscription_uuid (UUID): UUID of the SubscriptionPlan in license-manager
        Returns:
            dict: Dictionary representation of json returned from API
        """
        try:
            endpoint = self.subscriptions_endpoint + str(customer_uuid)
            response = self.client.get(endpoint, timeout=45)
            return response.json()
        except requests.exceptions.HTTPError as exc:
            logger.exception(exc)
            raise