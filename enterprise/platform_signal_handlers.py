"""
Signal handlers for platform-emitted Django signals consumed by edx-enterprise.
"""
import logging

from consent.models import DataSharingConsent
from enterprise.models import PendingEnterpriseCustomerUser

log = logging.getLogger(__name__)


def handle_user_retirement(sender, user, retired_username, retired_email, **kwargs):  # pylint: disable=unused-argument
    """
    Handle USER_RETIRE_LMS_CRITICAL signal to retire enterprise-specific user data.

    This handler performs two retirement operations:
    1. Retires DataSharingConsent records by replacing the username with the retired username.
    2. Retires PendingEnterpriseCustomerUser records by replacing the email with the retired email.

    Arguments:
        sender: the class that sent the signal (unused).
        user (User): the Django User being retired.
        retired_username (str): the anonymised username to substitute in consent records.
        retired_email (str): the anonymised email to substitute in pending enterprise records.
        **kwargs: forward-compatible catch-all for additional signal kwargs.
    """
    log.info(
        "Retiring enterprise data for user %s (retired_username=%s)",
        user.id,
        retired_username,
    )

    dsc_count = DataSharingConsent.objects.filter(
        username=user.username
    ).update(username=retired_username)
    log.info(
        "Retired %d DataSharingConsent record(s) for user %s",
        dsc_count,
        user.id,
    )

    pending_count = PendingEnterpriseCustomerUser.objects.filter(
        user_email=user.email
    ).update(user_email=retired_email)
    log.info(
        "Retired %d PendingEnterpriseCustomerUser record(s) for user %s",
        pending_count,
        user.id,
    )
