# -*- coding: utf-8 -*-
"""
Fake responses for ecommerce api.
"""

from __future__ import absolute_import, unicode_literals

import mock


def setup_post_order_to_ecommerce(client_mock):
    """
    Set up the Ecommerce API client for post_order_to_ecommerce.
    """
    dummy_order_details_mock = mock.MagicMock()
    dummy_order_details_mock.return_value = {
        'order': {
            'number': 'ORD:100023'
        },
    }
    order_details_mock = mock.MagicMock()
    method_name = 'baskets.post'
    attrs = {method_name: dummy_order_details_mock}
    order_details_mock.configure_mock(**attrs)
    client_mock.return_value = order_details_mock
