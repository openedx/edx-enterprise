"""
Utility functions for the Enterprise API.
"""
from django.conf import settings
from django.contrib import auth
from django.utils.translation import gettext as _

from enterprise.constants import (
    ENTERPRISE_CATALOG_ADMIN_ROLE,
    ENTERPRISE_DASHBOARD_ADMIN_ROLE,
    ENTERPRISE_REPORTING_CONFIG_ADMIN_ROLE,
)
from enterprise.models import (
    EnterpriseCustomer,
    EnterpriseCustomerCatalog,
    EnterpriseCustomerInviteKey,
    EnterpriseCustomerReportingConfiguration,
    EnterpriseCustomerUser,
    EnterpriseFeatureRole,
    EnterpriseFeatureUserRoleAssignment,
    EnterpriseGroup,
)

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
