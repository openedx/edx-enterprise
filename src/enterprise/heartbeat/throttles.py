"""
Throttles for heartbeat API endpoints.
"""
from rest_framework.throttling import UserRateThrottle


class HeartbeatRateThrottle(UserRateThrottle):
    """
    Throttle class for streamlining heartbeat traffic to manage server load.
    """
    scope = 'heartbeat'
    rate = '60/min'
