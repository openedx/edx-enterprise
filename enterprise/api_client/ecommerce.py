"""
Client for communicating with the E-Commerce API.
"""

import logging
from urllib.parse import urljoin

from requests.exceptions import ConnectionError, RequestException, Timeout  # pylint: disable=redefined-builtin

from django.conf import settings
from django.utils.translation import gettext as _

from enterprise.api_client.client import NoAuthAPIClient
from enterprise.utils import NotConnectedToOpenEdX, format_price

try:
    from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers
except ImportError:
    configuration_helpers = None

try:
    from openedx.core.djangoapps.commerce.utils import get_ecommerce_api_client
except ImportError:
    get_ecommerce_api_client = None

LOGGER = logging.getLogger(__name__)


class EcommerceApiClient:
    """
    The API client to make calls to the E-Commerce API.
    """
    def __init__(self, user):
        """
        Create an E-Commerce API client, authenticated with the API token.

        This method retrieves an authenticated API client that can be used
        to access the ecommerce API. It raises an exception to be caught at
        a higher level if the package doesn't have OpenEdX resources available.
        """
        if get_ecommerce_api_client is None or configuration_helpers is None:
            raise NotConnectedToOpenEdX(
                _('To get a ecommerce_api_client, this package must be '
                  'installed in an Open edX environment.')
            )

        self.user = user
        self.client = get_ecommerce_api_client(user)
        self.API_BASE_URL = configuration_helpers.get_value(  # pylint: disable=invalid-name
            'ECOMMERCE_API_URL', settings.ECOMMERCE_API_URL
        )

    def get_course_final_price(self, mode, currency='$', enterprise_catalog_uuid=None):
        """
        Get course mode's SKU discounted price after applying any entitlement available for this user.

        Returns:
            str: Discounted price of the course mode.
        """
        api_url = urljoin(f"{self.API_BASE_URL}/", "baskets/calculate/")
        try:
            response = self.client.get(
                api_url,
                params={
                    "sku": [mode['sku']],
                    "username": self.user.username,
                    "catalog": enterprise_catalog_uuid,
                }
            )
            response.raise_for_status()
            price_details = response.json()
        except (RequestException, ConnectionError, Timeout) as exc:
            LOGGER.exception('Failed to get price details for sku %s due to: %s', mode['sku'], str(exc))
            price_details = {}
        price = price_details.get('total_incl_tax', mode['min_price'])
        if price != mode['min_price']:
            return format_price(price, currency)
        return mode['original_price']

    def create_manual_enrollment_orders(self, enrollments):
        """
        Calls ecommerce to create orders for the manual enrollments passed in.

        `enrollments` should be a list of enrollments with the following format::

            {
                "lms_user_id": <int>,
                "username": <str>,
                "email": <str>,
                "course_run_key": <str>
            }

        Since `student.CourseEnrollment` lives in LMS, we're just passing
        around dicts of the relevant information.
        """
        api_url = urljoin(f"{self.API_BASE_URL}/", "manual_course_enrollment_order")
        try:
            response = self.client.post(api_url, json={"enrollments": enrollments})
            response.raise_for_status()
            order_response = response.json()
            order_creations = order_response["orders"]
            successful_creations = [order for order in order_creations if order["status"] == "success"]
            failed_creations = [order for order in order_creations if order["status"] == "failure"]
            if successful_creations:
                LOGGER.info(
                    "Successfully created orders for the following manual enrollments. %s",
                    successful_creations
                )
            if failed_creations:
                LOGGER.error(
                    "Failed to created orders for the following manual enrollments. %s",
                    failed_creations
                )
        except (RequestException, ConnectionError, Timeout) as exc:
            LOGGER.exception(
                "Failed to create order for manual enrollments for the following enrollments: %s. Reason: %s",
                enrollments,
                str(exc)
            )


class NoAuthEcommerceClient(NoAuthAPIClient):
    """
    The E-Commerce API client without authentication.
    """
    API_BASE_URL = settings.ECOMMERCE_PUBLIC_URL_ROOT
    APPEND_SLASH = False
