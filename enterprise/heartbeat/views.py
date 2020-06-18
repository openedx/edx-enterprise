"""
Views for enterprise heartbeat check.
"""
from logging import getLogger

from rest_framework.decorators import api_view, throttle_classes

from django.http import JsonResponse

from enterprise.heartbeat.throttles import HeartbeatRateThrottle
from enterprise.heartbeat.utils import run_checks

LOGGER = getLogger(__name__)


@api_view(['GET'])
@throttle_classes([HeartbeatRateThrottle])
def heartbeat(_):
    """
    Simple view that an external service can use to check if the app is up.

    Returns:
         (JsonResponse): A json doc of service id: status or message. If the status for any service
         is anything other than True,it returns HTTP code 503 (Service Unavailable);
         otherwise, it returns 200.
    """
    all_okay, response = run_checks()
    status_code = 200 if all_okay else 503

    return JsonResponse(response, status=status_code)
