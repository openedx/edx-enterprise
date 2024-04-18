"""
API clients to communicate with Braze services.
"""
import logging

from braze.client import BrazeClient

from django.conf import settings

logger = logging.getLogger(__name__)

ENTERPRISE_BRAZE_ALIAS_LABEL = 'Enterprise'  # Do Not change this, this is consistent with other uses across edX repos.


class BrazeAPIClient(BrazeClient):
    """
    API client for calls to Braze.
    """
    def __init__(self):
        braze_api_key = getattr(settings, 'EDX_BRAZE_API_KEY', None)
        braze_api_url = getattr(settings, 'EDX_BRAZE_API_SERVER', None)
        required_settings = ['EDX_BRAZE_API_KEY', 'EDX_BRAZE_API_SERVER']
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

    def generate_mailto_link(self, emails):
        """
        Generate a mailto link for the given emails.
        """
        if emails:
            return f'mailto:{",".join(emails)}'

        return None

    def create_recipient(
        self,
        user_email,
        lms_user_id,
        trigger_properties=None,
    ):
        """
        Create a recipient object using the given user_email and lms_user_id.
        Identifies the given email address with any existing Braze alias records
        via the provided ``lms_user_id``.
        """

        user_alias = {
            'alias_label': ENTERPRISE_BRAZE_ALIAS_LABEL,
            'alias_name': user_email,
        }

        # Identify the user alias in case it already exists. This is necessary so
        # we don't accidentally create a duplicate Braze profile.
        self.identify_users([{
            'external_id': lms_user_id,
            'user_alias': user_alias
        }])

        attributes = {
            "user_alias": user_alias,
            "email": user_email,
            "is_enterprise_learner": True,
            "_update_existing_only": False,
        }

        return {
            'external_user_id': lms_user_id,
            'attributes': attributes,
            # If a profile does not already exist, Braze will create a new profile before sending a message.
            'send_to_existing_only': False,
            'trigger_properties': trigger_properties or {},
        }

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
