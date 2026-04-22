"""
Django tasks.
"""

from datetime import timedelta
from logging import getLogger

from celery import shared_task
from edx_django_utils.monitoring import set_code_owner_attribute

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.db import IntegrityError, transaction
from django.db.models.functions import Lower

from enterprise import constants
from enterprise.api_client.braze import ENTERPRISE_BRAZE_ALIAS_LABEL, MAX_NUM_IDENTIFY_USERS_ALIASES, BrazeAPIClient
from enterprise.api_client.enterprise_catalog import EnterpriseCatalogApiClient
from enterprise.constants import SSO_BRAZE_CAMPAIGN_ID
from enterprise.utils import batch_dict, get_enterprise_customer, localized_utcnow, send_email_notification_message

LOGGER = getLogger(__name__)
User = get_user_model()

braze_client_class = BrazeAPIClient

try:
    from braze.exceptions import BrazeClientError
except ImportError:
    class BrazeClientError(Exception):
        """Fallback Braze client error when braze package is unavailable."""


def _get_braze_campaign_id(campaign_setting_name):
    """Return the configured Braze campaign id after validating required settings."""
    if not getattr(settings, 'ENTERPRISE_BRAZE_API_KEY', None) or not getattr(settings, 'EDX_BRAZE_API_SERVER', None):
        error_msg = 'Missing required Braze settings for admin invite email'
        LOGGER.error(error_msg)
        raise ValueError(error_msg)

    braze_campaign_id = getattr(settings, campaign_setting_name, None)
    if not braze_campaign_id:
        error_msg = f'Missing {campaign_setting_name} setting for admin invite email'
        LOGGER.error(error_msg)
        raise ValueError(error_msg)
    return braze_campaign_id


def _split_identified_and_anonymous_recipients(recipient_emails, campaign_setting_name):
    """Split recipient emails into identified-user payloads and anonymous email list."""
    normalized_emails = [
        email.strip().lower()
        for email in recipient_emails
        if email and email.strip()
    ]

    users_by_email = {
        user.email_lower: user
        for user in User.objects.annotate(email_lower=Lower('email')).filter(email_lower__in=normalized_emails)
    }

    is_learner_campaign = campaign_setting_name == constants.BRAZE_LEARNER_INVITE_CAMPAIGN_SETTING
    identified_recipients = []
    anonymous_emails = []

    for email in recipient_emails:
        normalized_email = (email or '').strip().lower()
        if not normalized_email:
            # Skip falsy or whitespace-only emails entirely
            continue
        user = users_by_email.get(normalized_email)
        if not user:
            anonymous_emails.append(normalized_email)
            continue

        attributes = {
            'email': normalized_email,
            'is_enterprise_learner': True,
        }
        if is_learner_campaign:
            attributes['first_name'] = (user.first_name or '').strip() or (user.username or '').strip()

        identified_recipients.append({
            'external_user_id': user.id,
            'send_to_existing_only': False,
            'attributes': attributes,
        })

    return identified_recipients, anonymous_emails


def _resolve_anonymous_recipients(braze_client_instance, anonymous_emails):
    """Return anonymous recipients, using alias creation when possible with fallback payloads."""
    if not anonymous_emails:
        return [], False

    try:
        braze_client_instance.create_braze_aliases_without_lookup(
            anonymous_emails,
            ENTERPRISE_BRAZE_ALIAS_LABEL,
        )
        return anonymous_emails, False
    except (BrazeClientError, AttributeError) as exc:
        LOGGER.warning(
            'Failed to create alias profiles for %d anonymous users: %s. Attempting direct-recipient fallback.',
            len(anonymous_emails),
            str(exc),
        )
        return [
            {
                'external_user_id': email,
                'send_to_existing_only': False,
                'attributes': {
                    'email': email,
                    'is_enterprise_learner': True,
                },
            }
            for email in anonymous_emails
        ], True


@shared_task
@set_code_owner_attribute
def send_enterprise_email_notification(
    enterprise_customer_uuid,
    admin_enrollment,
    email_items,
):
    """
    Send enrollment email notifications to specified learners

    Arguments:
        * enterprise_customer_uuid (UUID)
        * admin_enrollment=False : If True, this indicates admin based enrollment (e.g., bulk enrollment)
        *
        * email_items: list of dictionary objects with keys:
        *   user (dict): a dict with either of the following forms:
              - 1: { 'first_name': name, 'username': user_name, 'email': email } (similar to a User object)
              - 2: { 'user_email' : user_email } (similar to a PendingEnterpriseCustomerUser object)
        *   enrolled_in (dict): name and optionally other keys needed by templates
        *   dashboard_url (str)
    """
    with mail.get_connection() as email_conn:
        for item in email_items:
            course_name = item['enrolled_in']['name']
            if 'username' in item['user']:
                username = item['user']['username']
            else:
                username = 'no_username_found'
            try:
                send_email_notification_message(
                    item['user'],
                    item['enrolled_in'],
                    item['dashboard_url'],
                    enterprise_customer_uuid,
                    email_connection=email_conn,
                    admin_enrollment=admin_enrollment,
                )
            except Exception as exc:  # pylint: disable=broad-except
                LOGGER.exception(
                    "Failed notifying user: {}"
                    "enterprise_customer_uuid: {}"
                    "of enterprise enrollment in course {}"
                    .format(username, enterprise_customer_uuid, course_name),
                    exc_info=exc,
                )


@shared_task
@set_code_owner_attribute
def create_enterprise_enrollment(course_id, enterprise_customer_user_id):
    """
    Create enterprise enrollment for user if course_id part of catalog for the ENT customer.
    """
    enterprise_customer_user = enterprise_customer_user_model().objects.get(
        id=enterprise_customer_user_id
    )
    # Prevent duplicate records from being created if possible
    # before we need to make a call to discovery
    if enterprise_course_enrollment_model().objects.filter(
            enterprise_customer_user=enterprise_customer_user,
            course_id=course_id,
    ).exists():
        LOGGER.info((
            "EnterpriseCourseEnrollment record exists for user %s "
            "on course %s. Exiting task."
        ), enterprise_customer_user.user_id, course_id)
        return

    enterprise_customer = enterprise_customer_user.enterprise_customer
    if enterprise_customer.catalog_contains_course(course_id):
        LOGGER.info((
            "Creating EnterpriseCourseEnrollment for user %s "
            "on course %s for enterprise_customer %s"
        ), enterprise_customer_user.user_id, course_id, enterprise_customer)

        # On Create we set the Source to be ENROLLMENT_TASK here.  This Source
        # is generalized from being just a B2C Source type because it is possible
        # to reach this task before the EnterpriseCustomerEnrollment is created
        # depending on timing.
        #
        # We have made changes elsewhere to avoid this issue, but in the mean time
        # we believe a Source of ENROLLMENT_TASK is more clear.

        try:
            enterprise_course_enrollment_model().objects.get_or_create(
                course_id=course_id,
                enterprise_customer_user=enterprise_customer_user,
                defaults={
                    'source': enterprise_enrollment_source_model().get_source(
                        enterprise_enrollment_source_model().ENROLLMENT_TASK,
                    ),
                }
            )
        except IntegrityError:
            LOGGER.exception(
                "IntegrityError on attempt at EnterpriseCourseEnrollment for user with id [%s] "
                "and course id [%s]", enterprise_customer_user.user_id, course_id,
            )


def enterprise_customer_user_model():
    """
    Returns the ``EnterpriseCustomerUser`` class.
    This function is needed to avoid circular ref issues when model classes call tasks in this module.
    """
    return apps.get_model('enterprise', 'EnterpriseCustomerUser')


def pending_enterprise_customer_user_model():
    """
    Returns the ``PendingEnterpriseCustomerUser`` class.
    This function is needed to avoid circular ref issues when model classes call tasks in this module.
    """
    return apps.get_model('enterprise', 'PendingEnterpriseCustomerUser')


def enterprise_customer_admin_model():
    """
    Returns the ``EnterpriseCustomerAdmin`` class.
    This function is needed to avoid circular ref issues when model classes call tasks in this module.
    """
    return apps.get_model('enterprise', 'EnterpriseCustomerAdmin')


def pending_enterprise_customer_admin_user_model():
    """
    Returns the ``PendingEnterpriseCustomerAdminUser`` class.
    This function is needed to avoid circular ref issues when model classes call tasks in this module.
    """
    return apps.get_model('enterprise', 'PendingEnterpriseCustomerAdminUser')


def enterprise_group_membership_model():
    """
    Returns the ``EnterpriseGroupMembership`` class.
    This function is needed to avoid circular ref issues when model classes call tasks in this module.
    """
    return apps.get_model('enterprise', 'EnterpriseGroupMembership')


def enterprise_course_enrollment_model():
    """
    Returns the ``EnterpriseCourseEnrollment`` class.
    This function is needed to avoid circular ref issues when model classes call tasks in this module.
    """
    return apps.get_model('enterprise', 'EnterpriseCourseEnrollment')


def enterprise_enrollment_source_model():
    """
    Returns the ``EnterpriseEnrollmentSource`` class.
    This function is needed to avoid circular ref issues when model classes call tasks in this module.
    """
    return apps.get_model('enterprise', 'EnterpriseEnrollmentSource')


@shared_task
@set_code_owner_attribute
def send_sso_configured_email(
    enterprise_customer_uuid,
):
    """
    Send email notifications when SSO orchestration is complete.

    Arguments:
        * enterprise_customer_uuid (UUID)
    """
    enterprise_customer = get_enterprise_customer(enterprise_customer_uuid)
    enterprise_slug = enterprise_customer.slug
    enterprise_name = enterprise_customer.name
    sender_alias = enterprise_customer.sender_alias
    contact_email = enterprise_customer.contact_email

    braze_campaign_id = SSO_BRAZE_CAMPAIGN_ID
    braze_trigger_properties = {
        'enterprise_customer_slug': enterprise_slug,
        'enterprise_customer_name': enterprise_name,
        'enterprise_sender_alias': sender_alias,
        'enterprise_contact_email': contact_email,
    }

    try:
        braze_client_instance = BrazeAPIClient()
        recipient = braze_client_instance.create_recipient_no_external_id(
            contact_email,
        )
        braze_client_instance.create_braze_alias(
            [contact_email],
            ENTERPRISE_BRAZE_ALIAS_LABEL,
        )
        braze_client_instance.send_campaign_message(
            braze_campaign_id,
            recipients=[recipient],
            trigger_properties=braze_trigger_properties,
        )
    except AttributeError as exc:
        message = (
            'Enterprise oauth integration email sending received an '
            f'exception for enterprise: {enterprise_name}.'
        )
        LOGGER.exception(message)
        raise exc
    except BrazeClientError as exc:
        message = (
            'Enterprise oauth integration email sending received an '
            f'exception for enterprise: {enterprise_name}.'
        )
        LOGGER.exception(message)
        raise exc


@shared_task(bind=True)
@set_code_owner_attribute
def send_enterprise_admin_invite_email(
    _,
    enterprise_customer_uuid,
    recipient_emails,
    campaign_setting_name,
    additional_trigger_properties=None,
):
    """
    Send enterprise admin invitation emails using Braze campaigns.

    Args:
        enterprise_customer_uuid (UUID): Enterprise customer UUID.
        recipient_emails (list[str] or str): Recipient email(s) to invite.
        campaign_setting_name (str): Setting name that stores the Braze campaign id.
        additional_trigger_properties (dict, optional): Additional properties to include in Braze trigger.

    The task builds Braze trigger properties, normalizes single-email input to a
    list, splits recipients into identified and anonymous users, and sends campaign
    messages for each recipient group.

    For anonymous recipients, it attempts alias creation first and falls back to
    direct-recipient payloads if alias creation fails.

    Raises:
        ValueError: If required Braze settings or campaign id are missing.
        BrazeClientError: If a Braze API operation fails.
    """
    enterprise_customer = get_enterprise_customer(enterprise_customer_uuid)
    enterprise_slug = enterprise_customer.slug
    enterprise_name = enterprise_customer.name
    sender_alias = enterprise_customer.sender_alias

    LOGGER.info(
        "Preparing admin invite email for enterprise: uuid=%s, slug='%s', name='%s'",
        enterprise_customer_uuid,
        enterprise_slug,
        enterprise_name,
    )

    if not isinstance(recipient_emails, list):
        recipient_emails = [recipient_emails]

    braze_trigger_properties = {
        'customer_slug': enterprise_slug or '',
        'enterprise_customer_name': enterprise_name or '',
        'enterprise_sender_alias': sender_alias or '',
    }
    if additional_trigger_properties:
        braze_trigger_properties.update(additional_trigger_properties)

    braze_campaign_id = _get_braze_campaign_id(campaign_setting_name)

    try:
        braze_client_instance = braze_client_class()

        identified_recipients, anonymous_emails = _split_identified_and_anonymous_recipients(
            recipient_emails,
            campaign_setting_name,
        )
        anonymous_recipients, used_anonymous_fallback = _resolve_anonymous_recipients(
            braze_client_instance,
            anonymous_emails,
        )

        if not identified_recipients and not anonymous_recipients:
            LOGGER.warning('No valid recipients found for enterprise %s. Cannot send campaign.', enterprise_name)
            return

        total_recipients = len(identified_recipients) + len(anonymous_recipients)
        LOGGER.info(
            'Sending enterprise admin invite email to %d recipients (%d identified, %d anonymous) for enterprise %s.',
            total_recipients,
            len(identified_recipients),
            len(anonymous_recipients),
            enterprise_name,
        )

        if anonymous_recipients:
            braze_client_instance.send_campaign_message(
                braze_campaign_id,
                recipients=anonymous_recipients,
                trigger_properties=braze_trigger_properties,
            )

        if identified_recipients:
            braze_client_instance.send_campaign_message(
                braze_campaign_id,
                recipients=identified_recipients,
                trigger_properties=braze_trigger_properties,
            )

        LOGGER.info(
            'Successfully sent admin invite email to %d recipients for enterprise %s (anonymous_fallback_used=%s)',
            total_recipients,
            enterprise_slug,
            used_anonymous_fallback,
        )
    except BrazeClientError:
        message = (
            'Enterprise admin invite email could not be sent '
            f'to {recipient_emails} for enterprise {enterprise_name}.'
        )
        LOGGER.exception(message)
        raise


def _get_admin_invite_reminder_config():
    """Return validated config values for admin invite reminder cadence and limits."""
    initial_delay_window = timedelta(days=7)
    reminder_cadence_window = timedelta(days=3)
    max_reminders = 1
    batch_size = 500
    return initial_delay_window, reminder_cadence_window, max_reminders, batch_size


def _get_pending_admin_invite_reminder_count(pending_admin):
    """Return reminder sends count based on reminder_sent_at history records."""
    return pending_admin.history.filter(
        history_type='~',
        reminder_sent_at__isnull=False,
    ).values_list('reminder_sent_at', flat=True).distinct().count()


def _is_pending_admin_user_existing_learner(pending_admin):
    """Return ``True`` when pending admin already has an active linked enterprise learner account."""
    return enterprise_customer_user_model().objects.filter(
        enterprise_customer=pending_admin.enterprise_customer,
        user_id__isnull=False,
        active=True,
        user_fk__email__iexact=pending_admin.user_email,
    ).exists()


def _has_pending_admin_user_activated(pending_admin):
    """Return ``True`` when pending admin already has an active enterprise admin record."""
    return enterprise_customer_admin_model().objects.filter(
        enterprise_customer_user__enterprise_customer=pending_admin.enterprise_customer,
        enterprise_customer_user__user_id__isnull=False,
        enterprise_customer_user__active=True,
        enterprise_customer_user__user_fk__email__iexact=pending_admin.user_email,
    ).exists()


def _get_pending_admin_invite_reminder_campaign_setting(is_existing_learner):
    """Return reminder campaign setting key for pending admin invites."""
    if (
        is_existing_learner and
        getattr(settings, constants.BRAZE_LEARNER_ADMIN_INVITE_REMINDER_CAMPAIGN_SETTING, None)
    ):
        return constants.BRAZE_LEARNER_ADMIN_INVITE_REMINDER_CAMPAIGN_SETTING
    return constants.BRAZE_ADMIN_INVITE_REMINDER_CAMPAIGN_SETTING


def _is_pending_admin_invite_due_for_reminder(
    pending_admin,
    now,
    initial_delay_window,
    reminder_cadence_window,
    max_reminders,
):
    """Return due status and current reminder count for a pending admin."""
    reminder_count = _get_pending_admin_invite_reminder_count(pending_admin)
    if reminder_count >= max_reminders:
        return False, reminder_count

    if reminder_count == 0:
        return pending_admin.created <= now - initial_delay_window, reminder_count

    last_reminder = pending_admin.reminder_sent_at or pending_admin.modified
    return last_reminder <= now - reminder_cadence_window, reminder_count  # pragma: no cover


def _get_invite_skip_reason(
    pending_admin,
    now,
    initial_delay_window,
    reminder_cadence_window,
    max_reminders,
    sent_customer_email_set,
):
    """
    Check if a pending admin should be skipped for reminders.

    Returns:
        (str, int): A tuple of (skip_reason, reminder_count) where skip_reason is one of
        'active', 'duplicate', 'max', 'not_due', or None if the pending admin should receive a reminder.
    """
    if _has_pending_admin_user_activated(pending_admin):
        return 'active', 0

    customer_email_key = (
        pending_admin.enterprise_customer_id,
        pending_admin.user_email.strip().lower(),
    )
    if customer_email_key in sent_customer_email_set:  # pragma: no cover
        return 'duplicate', 0

    due_for_reminder, reminder_count = _is_pending_admin_invite_due_for_reminder(
        pending_admin, now, initial_delay_window, reminder_cadence_window, max_reminders,
    )
    if not due_for_reminder:
        reason = 'max' if reminder_count >= max_reminders else 'not_due'
        return reason, reminder_count

    return None, reminder_count


def _send_reminder_for_invite(pending_admin, reminder_count):
    """
    Send a reminder email for a single pending admin and update tracking.

    Returns the (customer_id, email) key for deduplication tracking.
    """
    is_existing_learner = _is_pending_admin_user_existing_learner(pending_admin)
    reminder_campaign_setting = _get_pending_admin_invite_reminder_campaign_setting(
        is_existing_learner,
    )

    send_enterprise_admin_invite_email.run(
        str(pending_admin.enterprise_customer.uuid),
        pending_admin.user_email,
        reminder_campaign_setting,
        additional_trigger_properties={
            'admin_invite_created_at': pending_admin.created.isoformat(),
            'reminder_number': reminder_count + 1,
        },
    )

    pending_admin.reminder_sent_at = localized_utcnow()
    pending_admin.save(update_fields=['reminder_sent_at', 'modified'])
    return (
        pending_admin.enterprise_customer_id,
        pending_admin.user_email.strip().lower(),
    )


@shared_task
@set_code_owner_attribute
def send_enterprise_admin_invite_reminders():
    """
    Send reminder Braze campaign messages for inactive pending admin invites.

    This task uses existing model timestamps and historical update rows to enforce:
    - initial wait after invite creation,
    - cadence between reminders,
    - maximum reminders per invite.
    """
    initial_delay_window, reminder_cadence_window, max_reminders, batch_size = _get_admin_invite_reminder_config()
    now = localized_utcnow()

    _get_braze_campaign_id(constants.BRAZE_ADMIN_INVITE_REMINDER_CAMPAIGN_SETTING)

    pending_admin_model = pending_enterprise_customer_admin_user_model()
    first_reminder_cutoff = now - initial_delay_window
    candidate_invite_ids = list(
        pending_admin_model.objects.filter(
            created__lte=first_reminder_cutoff,
        ).order_by('created').values_list('id', flat=True)[:batch_size]
    )

    counters = {'sent': 0, 'skipped_active': 0, 'skipped_not_due': 0, 'skipped_max': 0, 'failures': 0}
    sent_customer_email_set = set()

    for invite_id in candidate_invite_ids:
        try:
            with transaction.atomic():
                pending_admin = pending_admin_model.objects.select_for_update().select_related(
                    'enterprise_customer'
                ).filter(id=invite_id).first()
                if not pending_admin:  # pragma: no cover
                    continue

                skip_reason, reminder_count = _get_invite_skip_reason(
                    pending_admin, now, initial_delay_window,
                    reminder_cadence_window, max_reminders, sent_customer_email_set,
                )
                if skip_reason:
                    LOGGER.info('SKIP: invite id=%s reason=%s', invite_id, skip_reason)
                    if skip_reason == 'active':
                        counters['skipped_active'] += 1
                    elif skip_reason == 'max':
                        counters['skipped_max'] += 1
                    elif skip_reason == 'not_due':  # pragma: no cover
                        counters['skipped_not_due'] += 1
                    continue

                LOGGER.info('SEND: invite id=%s reminder #%d', invite_id, reminder_count + 1)
                customer_email_key = _send_reminder_for_invite(pending_admin, reminder_count)
                sent_customer_email_set.add(customer_email_key)
                counters['sent'] += 1
        except (BrazeClientError, ValueError):
            counters['failures'] += 1
            LOGGER.exception('Failed sending admin invite reminder for invite id=%s', invite_id)

    LOGGER.info(
        'Processed %d pending admin invites for reminders '
        '(sent=%d skipped_active=%d skipped_not_due=%d skipped_max=%d failures=%d).',
        len(candidate_invite_ids), counters['sent'], counters['skipped_active'],
        counters['skipped_not_due'], counters['skipped_max'], counters['failures'],
    )

    return {'processed': len(candidate_invite_ids), **counters}


def _recipients_for_identified_users(
    user_id_by_email,
    maximum_aliases_per_batch=MAX_NUM_IDENTIFY_USERS_ALIASES,
    alias_label=ENTERPRISE_BRAZE_ALIAS_LABEL
):
    """
    Helper function for create_recipients that takes a dictionary of user_email keys and
    user_id values, batches them in groups of the maximum number of users alias based
    on the braze documentation, and destructures the individual recipient values from
    recipients_by_email and returns a list of recipients.

    Arguments:
        * user_id_by_email (dict): A dictionary of user_email key and user_id values
        * maximum_aliases_per_batch (int):  An integer denoting the max allowable aliases to identify
                                            per create_recipients call to braze.
                                            Default is MAX_NUM_IDENTIFY_USERS_ALIASES
        * alias_label (string): A string denoting the alias label requried by braze.
                                Default is ENTERPRISE_BRAZE_ALIAS_LABEL

    Return:
        * recipients (list): A list of dictionary recipients

    Example:
        Input:
        user_id_by_email = {
        'test@gmail.com': 12345
        }
        maximum_aliases_per_batch: 50
        alias_label: Titans
        Output: [
            {
                'external_user_id: 12345,
                'attributes: {
                    'user_alias': {
                        'external_id': 12345,
                        'alias_label': 'Titans'
                    },
                },
            },
        ]
    """
    braze_client_instance = BrazeAPIClient()
    recipients = []
    LOGGER.info(
        '_recipients_for_identified_users_1: user_id_by_email: {%s}, '
        'maximum_aliases_per_batch: {%s}, alias_label: {%s} ',
        user_id_by_email,
        maximum_aliases_per_batch,
        alias_label
    )
    for user_id_by_email_chunk in batch_dict(user_id_by_email, maximum_aliases_per_batch):
        LOGGER.info(
            '_recipients_for_identified_users_2: user_id_by_email_chunk: {%s} ',
            user_id_by_email_chunk
        )
        recipients_by_email = braze_client_instance.create_recipients(
            alias_label,
            user_id_by_email=user_id_by_email_chunk
        )
        LOGGER.info(
            '_recipients_for_identified_users_3: recipients_by_email: {%s} ',
            recipients_by_email
        )
        recipients.extend(recipients_by_email.values())
    LOGGER.info(
        '_recipients_for_identified_users_4: recipients: {%s} ',
        recipients
    )
    return recipients


@shared_task
@set_code_owner_attribute
def send_group_membership_invitation_notification(
    enterprise_customer_uuid,
    membership_uuids,
    act_by_date,
    catalog_uuid
):
    """
    Send braze email notification when member is invited to a group.

    Arguments:
        * enterprise_customer_uuid (string)
        * memberships (list)
        * act_by_date (datetime)
        * catalog_uuid (string)
    """
    enterprise_customer = get_enterprise_customer(enterprise_customer_uuid)
    braze_client_instance = BrazeAPIClient()
    enterprise_catalog_client = EnterpriseCatalogApiClient()
    braze_trigger_properties = {}
    contact_email = enterprise_customer.contact_email
    enterprise_customer_name = enterprise_customer.name
    braze_trigger_properties['contact_admin_link'] = braze_client_instance.generate_mailto_link(contact_email)
    braze_trigger_properties['enterprise_customer_name'] = enterprise_customer_name
    braze_trigger_properties[
        'catalog_content_count'
    ] = enterprise_catalog_client.get_catalog_content_count(catalog_uuid)

    braze_trigger_properties['act_by_date'] = act_by_date.strftime('%B %d, %Y')
    pecu_emails = []
    user_id_by_email = {}
    membership_records = enterprise_group_membership_model().objects.filter(uuid__in=membership_uuids)
    for group_membership in membership_records:
        if group_membership.pending_enterprise_customer_user is not None:
            pecu_emails.append(group_membership.pending_enterprise_customer_user.user_email)
        else:
            LOGGER.info(
                'send_group_membership_invitation_notification_1: user_email: {%s}, user_id: {%s} ',
                group_membership.enterprise_customer_user.user_email,
                group_membership.enterprise_customer_user.user_id
            )
            user_id_by_email[
                group_membership.enterprise_customer_user.user_email
            ] = group_membership.enterprise_customer_user.user_id
    recipients = []
    for pecu_email in pecu_emails:
        recipients.append(braze_client_instance.create_recipient_no_external_id(pecu_email))
    if pecu_emails:
        braze_client_instance.create_braze_alias(
            pecu_emails,
            ENTERPRISE_BRAZE_ALIAS_LABEL,
        )
    LOGGER.info(
        'send_group_membership_invitation_notification_2: user_id_by_email: {%s} ',
        user_id_by_email,
    )
    recipients.extend(_recipients_for_identified_users(user_id_by_email))
    LOGGER.info(
        'send_group_membership_invitation_notification_3: recipients: {%s} ',
        recipients
    )
    try:
        braze_client_instance.send_campaign_message(
            settings.BRAZE_GROUPS_INVITATION_EMAIL_CAMPAIGN_ID,
            recipients=recipients,
            trigger_properties=braze_trigger_properties,
        )
    except BrazeClientError as exc:
        message = (
            "Groups learner invitation email could not be sent "
            f"to {recipients} for enterprise {enterprise_customer_name}."
        )
        membership_records.update(
            status=constants.GROUP_MEMBERSHIP_EMAIL_ERROR_STATUS,
            errored_at=localized_utcnow())
        LOGGER.exception(message)
        raise exc


@shared_task
@set_code_owner_attribute
def send_group_membership_removal_notification(enterprise_customer_uuid, membership_uuids, catalog_uuid):
    """
    Send braze email notification when learner is removed from a group.

    Arguments:
        * enterprise_customer_uuid (string)
        * group_membership_uuid (string)
    """
    enterprise_customer = get_enterprise_customer(enterprise_customer_uuid)
    braze_client_instance = BrazeAPIClient()
    enterprise_catalog_client = EnterpriseCatalogApiClient()
    braze_trigger_properties = {}
    contact_email = enterprise_customer.contact_email
    enterprise_customer_name = enterprise_customer.name
    braze_trigger_properties['contact_admin_link'] = braze_client_instance.generate_mailto_link(contact_email)
    braze_trigger_properties['enterprise_customer_name'] = enterprise_customer_name
    braze_trigger_properties[
        'catalog_content_count'
    ] = enterprise_catalog_client.get_catalog_content_count(catalog_uuid)
    pecu_emails = []
    user_id_by_email = {}
    membership_records = enterprise_group_membership_model().all_objects.filter(uuid__in=membership_uuids)
    for group_membership in membership_records:
        if group_membership.pending_enterprise_customer_user is not None:
            pecu_emails.append(group_membership.pending_enterprise_customer_user.user_email)
        else:
            LOGGER.info(
                'send_group_membership_removal_notification_1: user_email: {%s}, user_id: {%s} ',
                group_membership.enterprise_customer_user.user_email,
                group_membership.enterprise_customer_user.user_id
            )
            user_id_by_email[
                group_membership.enterprise_customer_user.user_email
            ] = group_membership.enterprise_customer_user.user_id

    recipients = []

    for pecu_email in pecu_emails:
        recipients.append(braze_client_instance.create_recipient_no_external_id(pecu_email))
    if pecu_emails:
        braze_client_instance.create_braze_alias(
            pecu_emails,
            ENTERPRISE_BRAZE_ALIAS_LABEL,
        )
    LOGGER.info(
        'send_group_membership_invitation_notification_2: user_id_by_email: {%s} ',
        user_id_by_email,
    )
    recipients.extend(_recipients_for_identified_users(user_id_by_email))
    LOGGER.info(
        'send_group_membership_removal_notification_3: recipients: {%s} ',
        recipients
    )
    try:
        braze_client_instance.send_campaign_message(
            settings.BRAZE_GROUPS_REMOVAL_EMAIL_CAMPAIGN_ID,
            recipients=recipients,
            trigger_properties=braze_trigger_properties,
        )
    except BrazeClientError as exc:
        message = (
            "Groups learner removal email could not be sent "
            f"to {recipients} for enterprise {enterprise_customer_name}."
        )
        membership_records.update(
            status=constants.GROUP_MEMBERSHIP_EMAIL_ERROR_STATUS,
            errored_at=localized_utcnow())
        LOGGER.exception(message)
        raise exc
