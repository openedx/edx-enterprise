# -*- coding: utf-8 -*-
"""
Throttle classes for enterprise API.
"""
from __future__ import absolute_import, unicode_literals

from rest_framework.throttling import UserRateThrottle

from enterprise.api.utils import get_service_usernames

SERVICE_USER_SCOPE = 'service_user'


class ServiceUserThrottle(UserRateThrottle):
    """
    A throttle allowing the service user to override rate limiting.
    """

    def allow_request(self, request, view):
        """
        Modify throttling for service users.

        Updates throttling rate if the request is coming from the service user, and
        defaults to UserRateThrottle's configured setting otherwise.

        Updated throttling rate comes from `DEFAULT_THROTTLE_RATES` key in `REST_FRAMEWORK`
        setting. service user throttling is specified in `DEFAULT_THROTTLE_RATES` by `service_user` key

        Example Setting:
            ```
            REST_FRAMEWORK = {
                ...
                'DEFAULT_THROTTLE_RATES': {
                    ...
                    'service_user': '50/day'
                }
            }
            ```
        """
        service_users = get_service_usernames()

        # User service user throttling rates for service user.
        if request.user.username in service_users:
            self.update_throttle_scope()

        return super(ServiceUserThrottle, self).allow_request(request, view)

    def update_throttle_scope(self):
        """
        Update throttle scope so that service user throttle rates are applied.
        """
        self.scope = SERVICE_USER_SCOPE
        self.rate = self.get_rate()
        self.num_requests, self.duration = self.parse_rate(self.rate)
