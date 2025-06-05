"""
Django tasks.
"""

from logging import getLogger

from celery import shared_task
from edx_django_utils.monitoring import set_code_owner_attribute

from django.apps import apps
from django.conf import settings
from django.core import mail
from django.db import IntegrityError

from enterprise import constants
from enterprise.api_client.braze import ENTERPRISE_BRAZE_ALIAS_LABEL, MAX_NUM_IDENTIFY_USERS_ALIASES, BrazeAPIClient
from enterprise.api_client.enterprise_catalog import EnterpriseCatalogApiClient
from enterprise.constants import SSO_BRAZE_CAMPAIGN_ID
from enterprise.utils import batch_dict, get_enterprise_customer, localized_utcnow, send_email_notification_message

LOGGER = getLogger(__name__)

try:
    from braze.exceptions import BrazeClientError
except ImportError:
    BrazeClientError = Exception


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
    except BrazeClientError as exc:
        message = (
            'Enterprise oauth integration email sending received an '
            f'exception for enterprise: {enterprise_name}.'
        )
        LOGGER.exception(message)
        raise exc


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
