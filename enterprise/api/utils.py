"""
Utility functions for the Enterprise API.
"""
import logging
from typing import List, Set

from django.conf import settings
from django.contrib import auth
from django.db import DatabaseError, transaction
from django.db.models import F
from django.db.models.functions import Lower
from django.utils.translation import gettext as _

from enterprise.constants import (
    BRAZE_ADMIN_INVITE_CAMPAIGN_SETTING,
    BRAZE_LEARNER_INVITE_CAMPAIGN_SETTING,
    ENTERPRISE_CATALOG_ADMIN_ROLE,
    ENTERPRISE_DASHBOARD_ADMIN_ROLE,
    ENTERPRISE_REPORTING_CONFIG_ADMIN_ROLE,
    AdminInviteStatus,
)
from enterprise.models import (
    EnterpriseCustomer,
    EnterpriseCustomerAdmin,
    EnterpriseCustomerCatalog,
    EnterpriseCustomerInviteKey,
    EnterpriseCustomerReportingConfiguration,
    EnterpriseCustomerUser,
    EnterpriseFeatureRole,
    EnterpriseFeatureUserRoleAssignment,
    EnterpriseGroup,
    PendingEnterpriseCustomerAdminUser,
)
from enterprise.tasks import send_enterprise_admin_invite_email

logger = logging.getLogger(__name__)


def get_existing_admin_emails(enterprise_customer: EnterpriseCustomer) -> Set[str]:
    """
    Retrieve normalized email addresses of existing ACTIVE enterprise admins.

    Only includes admins who have:
    1. An EnterpriseCustomerAdmin record
    2. An active EnterpriseCustomerUser (active=True)

    Args:
        enterprise_customer: The enterprise customer instance.

    Returns:
        Set of lowercased email addresses of active admins.

    Raises:
        DatabaseError: If database query fails.

    Example:
        >>> emails = get_existing_admin_emails(customer)
        >>> 'admin@example.com' in emails
        True
    """
    try:
        # Return emails of admins who have active ECU
        # Roles are not considered in customer admin lookup
        return set(
            EnterpriseCustomerAdmin.objects.filter(
                enterprise_customer_user__enterprise_customer=enterprise_customer,
                enterprise_customer_user__active=True
            )
            .annotate(email_l=Lower(F("enterprise_customer_user__user_fk__email")))
            .values_list("email_l", flat=True)
        )
    except DatabaseError:
        logger.exception(
            "Database error retrieving existing admin emails for enterprise customer: %s",
            enterprise_customer.uuid,
        )
        raise


def get_existing_pending_emails(
    enterprise_customer: EnterpriseCustomer,
    normalized_emails: List[str]
) -> Set[str]:
    """
    Retrieve normalized email addresses of pending admin invitations.

    Args:
        enterprise_customer: The enterprise customer instance.
        normalized_emails: List of normalized email addresses to check.

    Returns:
        Set of lowercased email addresses that have pending invitations.

    Raises:
        DatabaseError: If database query fails.

    Example:
        >>> pending = get_existing_pending_emails(customer, ['user@example.com'])
        >>> 'user@example.com' in pending
        True
    """
    try:
        return set(
            PendingEnterpriseCustomerAdminUser.objects.filter(
                enterprise_customer=enterprise_customer,
            )
            .annotate(email_l=Lower(F("user_email")))
            .filter(email_l__in=normalized_emails)
            .values_list("email_l", flat=True)
        )
    except DatabaseError:
        logger.exception(
            "Database error retrieving existing pending emails for enterprise customer: %s",
            enterprise_customer.uuid,
        )
        raise


def create_pending_invites(
    enterprise_customer: EnterpriseCustomer,
    emails_to_invite: List[str]
) -> List[PendingEnterpriseCustomerAdminUser]:
    """
    Create pending admin invitations and trigger email notifications.

    Creates PendingEnterpriseCustomerAdminUser records for new admin invites
    and enqueues Braze email tasks to be sent after transaction commits.

    Args:
        enterprise_customer: The enterprise customer instance.
        emails_to_invite: List of normalized email addresses to invite.

    Returns:
        List of created PendingEnterpriseCustomerAdminUser instances.

    Raises:
        DatabaseError: If database operation fails.
        ValueError: If emails_to_invite is empty.
        RuntimeError: If called outside a transaction.atomic block.

    Note:
        - Caller must wrap in transaction.atomic() to ensure atomicity
        - Uses get_or_create per email to avoid duplicate invite emails in race conditions
        - Emails are queued via transaction.on_commit() to send after transaction commits
        - Emails are routed to different Braze campaigns based on EnterpriseCustomerUser existence
          determined at invite creation time (before transaction commits)
        - This ensures emails only send if database changes succeed

    Example:
        >>> with transaction.atomic():
        ...     invites = create_pending_invites(customer, ['new@example.com'])
        >>> len(invites) > 0
        True
    """
    if not emails_to_invite:
        raise ValueError("emails_to_invite cannot be empty")

    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError("create_pending_invites must be called inside transaction.atomic().")

    def _enqueue_email_jobs(customer, invites, ecu_emails):
        """Enqueue invite emails, routing to appropriate Braze campaigns."""
        if not invites:
            return

        try:
            created_invite_emails = [invite.user_email for invite in invites]

            # Split emails based on pre-determined ECU existence
            # Using existing_ecu_emails captured before transaction to avoid race conditions
            learner_emails = []
            new_admin_emails = []
            for email in created_invite_emails:
                if email in ecu_emails:
                    learner_emails.append(email)
                else:
                    new_admin_emails.append(email)

            # Send to existing learners with learner campaign
            if learner_emails:
                send_enterprise_admin_invite_email.delay(
                    str(customer.uuid),
                    learner_emails,
                    campaign_setting_name=BRAZE_LEARNER_INVITE_CAMPAIGN_SETTING
                )

            # Send to new admins with admin campaign
            if new_admin_emails:
                send_enterprise_admin_invite_email.delay(
                    str(customer.uuid),
                    new_admin_emails,
                    campaign_setting_name=BRAZE_ADMIN_INVITE_CAMPAIGN_SETTING
                )

        except Exception:  # pylint: disable=broad-except
            # Log email queueing failures but don't fail the transaction
            # Invites are created successfully, emails can be re-sent manually
            logger.exception(
                "Failed to enqueue admin invite emails for enterprise customer: %s. "
                "Invite count: %d",
                customer.uuid,
                len(invites)
            )

    try:
        # Query existing active EnterpriseCustomerUsers BEFORE creating invites to determine routing
        # This prevents race conditions where ECU is created between invite and email sending
        existing_ecu_emails = set(
            EnterpriseCustomerUser.objects.filter(
                enterprise_customer=enterprise_customer,
                user_id__isnull=False,
                active=True,
            ).select_related('user_fk').annotate(
                email_lower=Lower('user_fk__email')
            ).filter(
                email_lower__in=emails_to_invite
            ).values_list('email_lower', flat=True)
        )

        created_invites = []
        for email in emails_to_invite:
            pending_invite, created = PendingEnterpriseCustomerAdminUser.objects.get_or_create(
                enterprise_customer=enterprise_customer,
                user_email=email,
            )
            if created:
                created_invites.append(pending_invite)

        transaction.on_commit(
            lambda: _enqueue_email_jobs(enterprise_customer, created_invites, existing_ecu_emails)
        )
        return created_invites

    except DatabaseError:
        logger.exception(
            "Database error creating pending invites for enterprise customer: %s",
            enterprise_customer.uuid,
        )
        raise


def get_invite_status(
    email: str,
    existing_admin_emails: Set[str],
    existing_pending_emails: Set[str]
) -> str:
    """
    Determine the invitation status for a given email address.

    Args:
        email (str): The email address to check.
        existing_admin_emails (Set[str]): Set of existing active admin email addresses.
        existing_pending_emails (Set[str]): Set of pending invitation email addresses.

    Returns:
        str: Status constant indicating email state:
            - AdminInviteStatus.EXISTING_ADMIN if user is already an active admin
            - AdminInviteStatus.PENDING_INVITE if invitation already sent
            - AdminInviteStatus.NEW_INVITE if this is a new invitation

    Example:
        >>> status = get_invite_status('new@example.com', set(), set())
        >>> status == 'invite sent'
        True
    """
    if email in existing_admin_emails:
        return AdminInviteStatus.EXISTING_ADMIN
    if email in existing_pending_emails:
        return AdminInviteStatus.PENDING_INVITE
    return AdminInviteStatus.NEW_INVITE


User = auth.get_user_model()
SERVICE_USERNAMES = (
    'ECOMMERCE_SERVICE_WORKER_USERNAME',
    'ENTERPRISE_SERVICE_WORKER_USERNAME'
)


class CourseRunProgressStatuses:
    """
    Class to group statuses that a course run can be in with respect to user progress.
    """

    IN_PROGRESS = 'in_progress'
    UPCOMING = 'upcoming'
    COMPLETED = 'completed'
    SAVED_FOR_LATER = 'saved_for_later'


def get_service_usernames():
    """
    Return the set of service usernames that are given extended permissions in the API.
    """
    if getattr(settings, 'ENTERPRISE_ALL_SERVICE_USERNAMES', None):
        return set(settings.ENTERPRISE_ALL_SERVICE_USERNAMES)

    return {getattr(settings, username, None) for username in SERVICE_USERNAMES}


def get_enterprise_customer_from_enterprise_group_id(group_id):
    """
    Get the enterprise customer id given an enterprise customer group id.
    """
    try:
        return str(EnterpriseGroup.objects.get(pk=group_id).enterprise_customer.uuid)
    except EnterpriseGroup.DoesNotExist:
        return None


def get_enterprise_customer_from_catalog_id(catalog_id):
    """
    Get the enterprise customer id given an enterprise customer catalog id.
    """
    try:
        return str(EnterpriseCustomerCatalog.objects.get(pk=catalog_id).enterprise_customer.uuid)
    except EnterpriseCustomerCatalog.DoesNotExist:
        return None


def get_ent_cust_from_report_config_uuid(uuid):
    """
    Get the enterprise customer id given an enterprise report configuration UUID.
    """
    try:
        return str(EnterpriseCustomerReportingConfiguration.objects.get(uuid=uuid).enterprise_customer.uuid)
    except EnterpriseCustomerReportingConfiguration.DoesNotExist:
        return None


def get_enterprise_customer_from_user_id(user_id):
    """
    Get the enterprise customer id given an user id
    """
    try:
        return str(EnterpriseCustomerUser.objects.get(user_id=user_id).enterprise_customer.uuid)
    except EnterpriseCustomerUser.DoesNotExist:
        return None


def create_message_body(email, enterprise_name, number_of_codes=None, notes=None):
    """
    Return the message body with extra information added by user.
    """
    if number_of_codes and notes:
        body_msg = _('{token_email} from {token_enterprise_name} has requested {token_number_codes} additional '
                     'codes. Please reach out to them.\nAdditional Notes:\n{token_notes}.').format(
                         token_email=email,
                         token_enterprise_name=enterprise_name,
                         token_number_codes=number_of_codes,
                         token_notes=notes)
    elif number_of_codes:
        body_msg = _('{token_email} from {token_enterprise_name} has requested {token_number_codes} additional '
                     'codes. Please reach out to them.').format(
                         token_email=email,
                         token_enterprise_name=enterprise_name,
                         token_number_codes=number_of_codes)
    elif notes:
        body_msg = _('{token_email} from {token_enterprise_name} has requested additional '
                     'codes. Please reach out to them.\nAdditional Notes:\n{token_notes}.').format(
                         token_email=email,
                         token_enterprise_name=enterprise_name,
                         token_notes=notes)
    else:
        body_msg = _('{token_email} from {token_enterprise_name} has requested additional codes.'
                     ' Please reach out to them.').format(
                         token_email=email,
                         token_enterprise_name=enterprise_name)
    return body_msg


def get_ent_cust_from_enterprise_customer_key(enterprise_customer_key):
    """
    Get the enterprise customer id given an enterprise customer key.
    """

    try:
        return str(EnterpriseCustomerInviteKey.objects.get(uuid=enterprise_customer_key).enterprise_customer_id)
    except EnterpriseCustomerInviteKey.DoesNotExist:
        return None


def delta_format(current, prior):
    """
    Formate delta of the given numbers.

    If the delta is positive, number is '+10'. If negative, change nothing, it will come through as '-10' by default.
    """
    delta = current - prior
    if delta >= 0:
        return f'+{delta}'
    else:
        return f'{delta}'


def percentage_format(number):
    """
    Turn float representation of percentage into a cleaner format (0.89 -> 89%)

    Arguments:
        number (float): Floating point number to format.

    Returns:
        (str): String representation of the float in percentage form.
    """
    return f'{number * 100:.0f}%'


def generate_prompt_for_learner_engagement_summary(engagement_data):
    """
    Generate an OpenAI prompt to get the summary of learner engagement from engagement data.

    Arguments:
         engagement_data (dict): A dictionary containing learner engagement numbers for some enterprise customer.

    Returns:
        (str): OpenAI prompt for getting engagement summary.
    """
    is_active = engagement_data['active_contract']
    data = {
        'enrolls': engagement_data['enrolls'],
        'enrolls_delta': delta_format(current=engagement_data['enrolls'], prior=engagement_data['enrolls_prior']),
        'engage': engagement_data['engage'],
        'engage_delta': delta_format(current=engagement_data['engage'], prior=engagement_data['engage_prior']),
        'hours': engagement_data['hours'],
        'hours_delta': delta_format(current=engagement_data['hours'], prior=engagement_data['hours_prior']),
        'passed': engagement_data['passed'],
        'passed_delta': delta_format(current=engagement_data['passed'], prior=engagement_data['passed_prior']),
    }

    # If active contract (or unknown).
    if is_active or is_active is None:
        prompt = settings.LEARNER_ENGAGEMENT_PROMPT_FOR_ACTIVE_CONTRACT
    else:
        # if enterprise customer does not have an active contract
        prompt = settings.LEARNER_ENGAGEMENT_PROMPT_FOR_NON_ACTIVE_CONTRACT

    return prompt.format(**data)


def generate_prompt_for_learner_progress_summary(progress_data):
    """
    Generate an OpenAI prompt to get the summary of learner progress from progress data.

    Arguments:
         progress_data (dict): A dictionary containing learner progress numbers for some enterprise customer.

    Returns:
        (str): OpenAI prompt for getting learner progress summary.
    """
    is_active = progress_data['active_subscription_plan']
    data = {
        'assigned_licenses': progress_data['assigned_licenses'],
        'assigned_licenses_percentage': percentage_format(progress_data['assigned_licenses_percentage']),
        'activated_licenses': progress_data['activated_licenses'],
        'activated_licenses_percentage': percentage_format(progress_data['activated_licenses_percentage']),
        'active_enrollments': progress_data['active_enrollments'],
        'at_risk_enrollment_less_than_one_hour': progress_data['at_risk_enrollment_less_than_one_hour'],
        'at_risk_enrollment_end_date_soon': progress_data['at_risk_enrollment_end_date_soon'],
        'at_risk_enrollment_dormant': progress_data['at_risk_enrollment_dormant'],
    }

    # If active contract (or unknown).
    if is_active or is_active is None:
        prompt = settings.LEARNER_PROGRESS_PROMPT_FOR_ACTIVE_CONTRACT
    else:
        # if enterprise customer does not have an active contract
        prompt = settings.LEARNER_PROGRESS_PROMPT_FOR_NON_ACTIVE_CONTRACT

    return prompt.format(**data)


def set_application_name_from_user_id(user_id):
    """
    Get the enterprise customer user's name given a user id.
    """
    try:
        user = User.objects.get(id=user_id)
        return f"{user.username}'s Enterprise Credentials"
    except User.DoesNotExist:
        return None


def has_api_credentials_enabled(enterprise_uuid):
    """
    Check whether the enterprise customer can access to api credentials or not
    """
    try:
        return (EnterpriseCustomer
                .objects.get(uuid=enterprise_uuid)
                .enable_generation_of_api_credentials)
    except EnterpriseCustomer.DoesNotExist:
        return False


def assign_feature_roles(user):
    """
    Add the ENTERPRISE_DASHBOARD_ADMIN_ROLE, ENTERPRISE_REPORTING_CONFIG_ADMIN_ROLE, ENTERPRISE_CATALOG_ADMIN_ROLE
    feature roles if the user does not already have them
    """
    roles_name = [ENTERPRISE_DASHBOARD_ADMIN_ROLE, ENTERPRISE_REPORTING_CONFIG_ADMIN_ROLE,
                  ENTERPRISE_CATALOG_ADMIN_ROLE]
    for role_name in roles_name:
        feature_role_object, __ = EnterpriseFeatureRole.objects.get_or_create(name=role_name)
        EnterpriseFeatureUserRoleAssignment.objects.get_or_create(user=user, role=feature_role_object)
