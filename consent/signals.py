"""
Django signal handlers for the consent module.
"""
from logging import getLogger

from consent.models import DataSharingConsent

logger = getLogger(__name__)

try:
    from openedx.core.djangoapps.user_api.accounts.signals import USER_RETIRE_LMS_CRITICAL
except ImportError:
    USER_RETIRE_LMS_CRITICAL = None


def retire_users_data_sharing_consent(sender, user, retired_username, **kwargs):  # pylint: disable=unused-argument
    """
    Handle USER_RETIRE_LMS_CRITICAL signal: retire DataSharingConsent username records.

    Idempotent: only updates records where username hasn't already been changed to the retired value.
    """
    DataSharingConsent.objects.filter(
        username=user.username,
    ).exclude(
        username=retired_username,
    ).update(username=retired_username)


if USER_RETIRE_LMS_CRITICAL is not None:
    USER_RETIRE_LMS_CRITICAL.connect(retire_users_data_sharing_consent)
