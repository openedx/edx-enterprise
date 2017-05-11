# -*- coding: utf-8 -*-
"""
Utilities to get details from the ecommerce API.
"""
from __future__ import absolute_import, unicode_literals

try:
    from openedx.core.djangoapps.commerce.utils import ecommerce_api_client, is_commerce_service_configured
except ImportError:
    def is_commerce_service_configured():
        """
        When we call this name, return False, since we couldn't import.
        """
        return False

    ecommerce_api_client = None


class EcommerceApiClient(object):
    """
    Object builds an API client to make calls to the ecommerce API.
    """

    def __init__(self, user):
        """
        Create an EcommerceApiClient, initialized with a JWT from the user passed in.
        """
        if ecommerce_api_client is not None and is_commerce_service_configured():
            self.client = ecommerce_api_client(user)
        else:
            self.client = None

    def get_single_coupon(self, coupon_id):
        """
        Get the details of a single coupon, identified by ID.

        If the client fails to retrieve the details of a coupon, as indicated
        by a raised exception, catch it and simply return an empty value. Depending
        on the exact architecture of the upstream client, an error could be of
        any number of given base classes, so we catch broadly, as specifying the entire
        set of exceptions that we'd need to look for would both be fragile and complex.
        """
        if self.client is None:
            return {}
        try:
            response = self.client.coupons(coupon_id).get()
        except Exception:  # pylint: disable=broad-except
            response = {}
        return response

    def get_coupons_by_enterprise_customer(self, enterprise_customer_uuid):
        """
        Get a list of the coupons associated with an EnterpriseCustomer.

        If the client fails to retrieve a list of coupons, as indicated by a
        raised exception, catch it and simply return an empty value. Depending
        on the exact architecture of the upstream client, an error could be of
        any number of given base classes, so we catch broadly, as specifying the entire
        set of exceptions that we'd need to look for would both be fragile and complex.
        """
        if self.client is None:
            return []
        results = []
        page = 1
        next_page = True
        try:
            while next_page:
                response = self.client.coupons.get(enterprise_customer=enterprise_customer_uuid, page=page)
                results += response.get('results', [])
                next_page = response.get('next')
                page += 1
        except Exception:  # pylint: disable=broad-except
            pass
        return results
