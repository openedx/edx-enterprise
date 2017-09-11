# -*- coding: utf-8 -*-
"""
Client for communicating with the E-Commerce API.
"""
from __future__ import absolute_import, unicode_literals

import logging

from requests.exceptions import ConnectionError, Timeout  # pylint: disable=redefined-builtin
from slumber.exceptions import SlumberBaseException

from django.utils.translation import ugettext as _

from enterprise.utils import NotConnectedToOpenEdX, format_price

try:
    from openedx.core.djangoapps.commerce.utils import ecommerce_api_client
except ImportError:
    ecommerce_api_client = None


LOGGER = logging.getLogger(__name__)


class EcommerceApiClient(object):
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

    def get_course_final_price(self, mode, currency='$'):
        """
        Get course mode's SKU discounted price after applying any entitlement available for this user.

        Returns:
            str: Discounted price of the course mode.

        """
        try:
            price_details = self.client.baskets.calculate.get(sku=[mode['sku']])
        except (SlumberBaseException, ConnectionError, Timeout) as exc:
            LOGGER.exception('Failed to get price details for sku %s due to: %s', mode['sku'], str(exc))
            price_details = {}
        price = price_details.get('total_incl_tax', mode['min_price'])
        if price != mode['min_price']:
            return format_price(price, currency)
        return mode['original_price']
