"""
API clients to communicate with Braze services.
"""
import logging

from django.conf import settings

logger = logging.getLogger(__name__)

try:
    from braze.client import BrazeClient
except ImportError:
    BrazeClient = None

ENTERPRISE_BRAZE_ALIAS_LABEL = 'Enterprise'  # Do Not change this, this is consistent with other uses across edX repos.
# https://www.braze.com/docs/api/endpoints/user_data/post_user_identify/
MAX_NUM_IDENTIFY_USERS_ALIASES = 50


class BrazeAPIClient(BrazeClient or object):
    """
    API client for calls to Braze.
    """
    def __init__(self):
        if BrazeClient:
            braze_api_key = getattr(settings, 'ENTERPRISE_BRAZE_API_KEY', None)
            braze_api_url = getattr(settings, 'EDX_BRAZE_API_SERVER', None)
            required_settings = ['ENTERPRISE_BRAZE_API_KEY', 'EDX_BRAZE_API_SERVER']
            for setting in required_settings:
                if not getattr(settings, setting, None):
                    msg = f'Missing {setting} in settings required for Braze API Client.'
                    logger.error(msg)
                    raise ValueError(msg)

            super().__init__(
                api_key=braze_api_key,
                api_url=braze_api_url,
                app_id='',
            )
        else:
            logger.warning('BrazeClient could not be imported, calls to Braze will not work')

    def generate_mailto_link(self, emails):
        """
        Generate a mailto link for the given emails.
        """
        if emails:
            return f'mailto:{",".join(emails)}'

        return None

    def create_recipient_no_external_id(self, user_email):
        """
        Create a Braze recipient dict identified only by an alias based on their email.
        """
        return {
            'attributes': {
                'email': user_email,
                'is_enterprise_learner': True,
            },
            'user_alias': {
                'alias_label': ENTERPRISE_BRAZE_ALIAS_LABEL,
                'alias_name': user_email,
            },
        }
