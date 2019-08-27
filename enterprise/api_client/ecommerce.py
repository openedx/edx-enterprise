# -*- coding: utf-8 -*-
"""
Client for communicating with the E-Commerce API.
"""
from __future__ import absolute_import, unicode_literals

import logging
from functools import reduce  # pylint: disable=redefined-builtin

from requests.exceptions import ConnectionError, Timeout  # pylint: disable=redefined-builtin
from slumber.exceptions import SlumberBaseException

from django.conf import settings
from django.contrib.auth.models import User
from django.utils.translation import ugettext as _

from enterprise.utils import NotConnectedToOpenEdX, format_price

try:
    from openedx.core.djangoapps.commerce.utils import ecommerce_api_client
except ImportError:
    ecommerce_api_client = None


LOGGER = logging.getLogger(__name__)


def get_ecommerce_api_client():
    """
    Create an ecommerce api client for `ecommerce_worker` user.
    """
    user = User.objects.get(username=settings.ECOMMERCE_SERVICE_WORKER_USERNAME)
    return EcommerceApiClient(user)


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

    def create_order_for_manual_course_enrollment(
            self,
            enrolled_learner_lms_user_id,
            enrolled_learner_username,
            enrolled_learner_email,
            enrolled_course_run_key,
    ):
        """
        Create an ecommerce order record for manually enrolled learner.
        """
        try:
            return self.client.manual_course_enrollment_order.post({
                'lms_user_id': enrolled_learner_lms_user_id,
                'username': enrolled_learner_username,
                'email': enrolled_learner_email,
                'course_run_key': enrolled_course_run_key,
            })
        except (SlumberBaseException, ConnectionError, Timeout) as exc:
            LOGGER.exception(
                '[Enterprise Manual Course Enrollment] Failed to create ecommerce order. Exception occurred: '
                'UserId: %s, User: %s, Email: %s, Course: %s, Exception: %s',
                enrolled_learner_lms_user_id,
                enrolled_learner_username,
                enrolled_learner_email,
                enrolled_course_run_key,
                exc
            )
            raise exc

    def fail_order_for_manual_course_enrollment(self, order_id):
        """
        Fail an existing completed ecommerce order.
        """
        resource = 'manual_course_enrollment_order'
        path = [resource, str(order_id)]
        order = reduce(getattr, path, self.client)

        try:
            return order.fail.put({
                'reason': "Learner's manual course enrollment failed"
            })
        except (SlumberBaseException, ConnectionError, Timeout) as exc:
            LOGGER.exception(
                '[Enterprise Manual Course Enrollment] Failed to update ecommerce order. Exception occurred: '
                'OrderId: %s, Exception: %s', order_id, exc
            )
            raise exc
