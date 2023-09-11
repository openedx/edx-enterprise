"""
API clients to communicate with Braze services.
"""
import logging

from braze.client import BrazeClient

from django.conf import settings

logger = logging.getLogger(__name__)


class BrazeAPIClient:
    """
    API client for calls to Braze.
    """
    def get_braze_client():  # pylint: disable=no-method-argument
        """ Returns a Braze client. """
        if not BrazeClient:
            return None

        # fetching them from edx-platform settings
        braze_api_key = getattr(settings, 'EDX_BRAZE_API_KEY', None)
        braze_api_url = getattr(settings, 'EDX_BRAZE_API_SERVER', None)

        if not braze_api_key or not braze_api_url:
            return None

        return BrazeClient(
            api_key=braze_api_key,
            api_url=braze_api_url,
            app_id='',
        )
