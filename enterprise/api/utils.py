# -*- coding: utf-8 -*-
"""
Utility functions for the Enterprise API.
"""
from __future__ import absolute_import, unicode_literals

from django.conf import settings

SERVICE_USERNAMES = (
    'ECOMMERCE_SERVICE_WORKER_USERNAME',
    'ENTERPRISE_SERVICE_WORKER_USERNAME'
)


def get_service_usernames():
    """
    Return the set of service usernames that are given extended permissions in the API.
    """
    return {getattr(settings, username, None) for username in SERVICE_USERNAMES}


def update_content_filters(combined_content_filter, new_content_filter):
    """
    Helper method for combining 2 content filter dicts
    """
    for filter_key, filter_value in new_content_filter.items():
        if filter_key in combined_content_filter:
            old_value = combined_content_filter[filter_key]
            if isinstance(filter_value, list):
                combined_content_filter[filter_key] = list(set(old_value) | set(filter_value))
            elif filter_value != old_value:
                combined_content_filter[filter_key] = [filter_value, old_value]
        else:
            combined_content_filter[filter_key] = filter_value
