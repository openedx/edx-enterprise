"""
Throttle classes for enterprise API.
"""

from rest_framework.throttling import UserRateThrottle

from enterprise.api.utils import get_service_usernames

SERVICE_USER_SCOPE = 'service_user'
HIGH_SERVICE_USER_SCOPE = 'high_service_user'


class BaseThrottle(UserRateThrottle):
    """
    Base throttle class with common functionality.
    """

    def allow_request(self, request, view):
        """
        Modify throttling for service users.

        Updates throttling rate if the request is coming from the service user, and defaults to UserRateThrottle's
        configured setting otherwise.

        Updated throttling rate comes from `DEFAULT_THROTTLE_RATES` key in `REST_FRAMEWORK` setting. specific user
        throttling is specified in `DEFAULT_THROTTLE_RATES` by it's corresponding key.

        .. code-block::

            REST_FRAMEWORK = {
                'DEFAULT_THROTTLE_RATES': {
                    'service_user': '50/day',
                    'high_service_user': '2000/minute',
                }
            }
        """
        service_users = get_service_usernames()

        # Update throttle scope if the request user is a service user.
        if request.user.username in service_users:
            self.update_throttle_scope()

        return super().allow_request(request, view)

    def get_scope(self):
        """
        Get the scope of the throttle.

        Raises:
            NotImplementedError: Must be implemented by subclasses
        """
        raise NotImplementedError("Subclasses must implement get_scope.")

    def update_throttle_scope(self):
        """
        Update throttle scope based on the specific subclass.
        """
        self.scope = self.get_scope()
        self.rate = self.get_rate()
        self.num_requests, self.duration = self.parse_rate(self.rate)


class ServiceUserThrottle(BaseThrottle):
    """
    A throttle allowing the service user to override rate limiting.
    """

    def get_scope(self):
        """
        Get the scope of the throttle.

        Returns:
            str: The scope of the throttle.
        """
        return SERVICE_USER_SCOPE


class HighServiceUserThrottle(BaseThrottle):
    """
    A throttle for high service users.
    """

    def get_scope(self):
        """
        Get the scope of the throttle.

        Returns:
            str: The scope of the throttle.
        """
        return HIGH_SERVICE_USER_SCOPE
