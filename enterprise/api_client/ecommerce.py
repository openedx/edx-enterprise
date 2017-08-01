# -*- coding: utf-8 -*-
"""
Client for communicating with the E-Commerce API.
"""
from __future__ import absolute_import, unicode_literals

import logging

from edx_rest_api_client.exceptions import HttpClientError
from requests.exceptions import HTTPError, Timeout

from django.contrib import messages
from django.utils.translation import ugettext as _

from enterprise.utils import NotConnectedToOpenEdX

try:
    from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers
except ImportError:
    configuration_helpers = None

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

    def get_course_final_price(self, mode):
        """
        Get course mode's SKU discounted price after applying any entitlement available for this user.

        Returns:
            str: Discounted price of the course mode.

        """
        endpoint = self.client.baskets.calculate
        price_details = endpoint.get(sku=[mode['sku']])
        price = price_details['total_incl_tax']
        if price != mode['min_price']:
            if int(price) == price:
                return '${}'.format(int(price))
            return '${:0.2f}'.format(price)
        return mode['original_price']

    def post_audit_order_to_ecommerce(self, request, sku):
        """
        Post an order for audit enrollment  for the user.

        Arguments:
            request (HttpRequest): Django request object
            sku (str): E-Commerce SKU for the course user is trying enroll

        Returns:
            str: E-Commerce order number for the enrollment.
        """
        try:
            response_data = self.client.baskets.post({
                'products': [{'sku': sku}],
                'checkout': True,
            })
        except (HTTPError, Timeout, HttpClientError):
            LOGGER.error(
                'Failed to post audit enrollment of user "{username}" in product "{sku}".'.format(
                    sku=sku,
                    username=request.user.username,
                )
            )
            messages.error(
                request,
                _(
                    'There was an error completing your enrollment in the course, please try again. '
                    'If the problem persists, contact {link_start}{platform_name} support{link_end}.',
                ).format(
                    link_start='<a href="{support_link}" target="_blank">'.format(
                        support_link=configuration_helpers.get_value('ENTERPRISE_SUPPORT_URL')
                    ),
                    platform_name=configuration_helpers.get_value('PLATFORM_NAME'),
                    link_end='</a>',
                ),
            )
            raise
        return response_data['order']['number']
