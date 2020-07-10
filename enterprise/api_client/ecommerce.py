# -*- coding: utf-8 -*-
"""
Client for communicating with the E-Commerce API.
"""

import logging

from edx_rest_api_client.client import EdxRestApiClient
from requests.exceptions import ConnectionError, Timeout  # pylint: disable=redefined-builtin
from slumber.exceptions import SlumberBaseException

from django.conf import settings
from django.utils.translation import ugettext as _

from enterprise.utils import NotConnectedToOpenEdX, format_price

try:
    from openedx.core.djangoapps.commerce.utils import ecommerce_api_client
except ImportError:
    ecommerce_api_client = None

LOGGER = logging.getLogger(__name__)


class EcommerceApiClient:
    """
    Object builds an API client to make calls to the E-Commerce API.
    """

    def __init__(self, user):
        """
        Create an E-Commerce API client, authenticated with the API token from Django settings.

        This method retrieves an authenticated API client that can be used
        to access the ecommerce API. It raises an exception to be caught at
        a higher level if the package doesn't have OpenEdX resources available.
        """
        if ecommerce_api_client is None:
            raise NotConnectedToOpenEdX(
                _('To get a ecommerce_api_client, this package must be '
                  'installed in an Open edX environment.')
            )

        self.user = user
        self.client = ecommerce_api_client(user)

    def get_course_final_price(self, mode, currency='$', enterprise_catalog_uuid=None):
        """
        Get course mode's SKU discounted price after applying any entitlement available for this user.

        Returns:
            str: Discounted price of the course mode.

        """
        try:
            price_details = self.client.baskets.calculate.get(
                sku=[mode['sku']],
                username=self.user.username,
                catalog=enterprise_catalog_uuid,
            )
        except (SlumberBaseException, ConnectionError, Timeout) as exc:
            LOGGER.exception('Failed to get price details for sku %s due to: %s', mode['sku'], str(exc))
            price_details = {}
        price = price_details.get('total_incl_tax', mode['min_price'])
        if price != mode['min_price']:
            return format_price(price, currency)
        return mode['original_price']

    def create_manual_enrollment_orders(self, enrollments):
        """
        Calls ecommerce to create orders for the manual enrollments passed in.

        `enrollments` should be a list of enrollments with the following format:
        {
            "lms_user_id": <int>,
            "username": <str>,
            "email": <str>,
            "course_run_key": <str>
        }

        Since `student.CourseEnrollment` lives in LMS, we're just passing around dicts of the relevant information.
        """
        try:
            order_response = self.client.manual_course_enrollment_order.post(
                {
                    "enrollments": enrollments
                }
            )
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
        except (SlumberBaseException, ConnectionError, Timeout) as exc:
            LOGGER.exception(
                "Failed to create order for manual enrollments for the following enrollments: %s. Reason: %s",
                enrollments,
                str(exc)
            )


class NoAuthEcommerceClient:
    """
    Class to build an E-Commerce client to make calls to the E-Commerce.
    """

    API_BASE_URL = settings.ECOMMERCE_PUBLIC_URL_ROOT
    APPEND_SLASH = False

    def __init__(self):
        """
        Create an E-Commerce client.
        """
        self.client = EdxRestApiClient(self.API_BASE_URL, append_slash=self.APPEND_SLASH)

    def get_health(self):
        """
        Retrieve health details for E-Commerce service.

        Returns:
            dict: Response containing E-Commerce service health.
        """
        return self.client.health.get()
