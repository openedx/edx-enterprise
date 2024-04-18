"""
Django tasks.
"""

from logging import getLogger

from braze.exceptions import BrazeClientError
from celery import shared_task
from edx_django_utils.monitoring import set_code_owner_attribute

from django.apps import apps
from django.core import mail
from django.db import IntegrityError

from enterprise.api_client.braze import BrazeAPIClient
from enterprise.constants import SSO_BRAZE_CAMPAIGN_ID
from enterprise.utils import (
    get_enterprise_customer,
    send_email_notification_message,
    unset_language_of_all_enterprise_learners,
)

LOGGER = getLogger(__name__)


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
        braze_client_instance = BrazeAPIClient.get_braze_client()
        braze_client_instance.send_campaign_message(
            braze_campaign_id,
            recipients=[contact_email],
            trigger_properties=braze_trigger_properties,
        )
    except BrazeClientError as exc:
        message = (
            'Enterprise oauth integration email sending received an '
            f'exception for enterprise: {enterprise_name}.'
        )
        LOGGER.exception(message)
        raise exc


@shared_task
@set_code_owner_attribute
def update_enterprise_learners_user_preference(enterprise_customer_uuid):
    """
    Update the user preference `pref-lang` attribute for all enterprise learners linked with an enterprise.

    Arguments:
        * enterprise_customer_uuid (UUID): uuid of an enterprise customer
    """
    unset_language_of_all_enterprise_learners(enterprise_customer_uuid)
