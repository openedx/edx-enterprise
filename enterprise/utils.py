# -*- coding: utf-8 -*-
"""
Utility functions for enterprise app.
"""
import datetime
import json
import logging
import re
from urllib.parse import urljoin
from uuid import UUID

import bleach
import pytz
import tableauserverclient as TSC
from edx_django_utils.cache import TieredCache
from edx_django_utils.cache import get_cache_key as get_django_cache_key
from edx_rest_api_client.exceptions import HttpClientError
from six.moves.urllib.parse import parse_qs, urlencode, urlparse, urlsplit, urlunsplit
from tableauserverclient.server.endpoint.exceptions import ServerResponseError

from django.apps import apps
from django.conf import settings
from django.contrib import auth
from django.core import mail
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.validators import validate_email
from django.db import utils
from django.db.models.query import QuerySet
from django.forms.models import model_to_dict
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.html import format_html
from django.utils.http import urlquote
from django.utils.text import slugify
from django.utils.translation import ugettext as _
from django.utils.translation import ungettext

from enterprise.constants import (
    ALLOWED_TAGS,
    DEFAULT_CATALOG_CONTENT_FILTER,
    LMS_API_DATETIME_FORMAT,
    LMS_API_DATETIME_FORMAT_WITHOUT_TIMEZONE,
    PATHWAY_CUSTOMER_ADMIN_ENROLLMENT,
    PROGRAM_TYPE_DESCRIPTION,
    CourseModes,
)

try:
    from openedx.features.enterprise_support.enrollments.utils import lms_enroll_user_in_course
except ImportError:
    lms_enroll_user_in_course = None

try:
    from openedx.core.djangoapps.course_groups.models import CourseUserGroup
    from openedx.core.djangoapps.enrollments.errors import CourseEnrollmentError
except ImportError:
    CourseUserGroup = None
    CourseEnrollmentError = None

try:
    from common.djangoapps.course_modes.models import CourseMode
except ImportError:
    CourseMode = None

try:
    from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers
except ImportError:
    configuration_helpers = None

try:
    from openedx.core.djangoapps.catalog.models import CatalogIntegration
except ImportError:
    CatalogIntegration = None

try:
    from lms.djangoapps.branding.api import get_logo_url
except ImportError:
    get_logo_url = None

try:
    from lms.djangoapps.branding.api import get_url
except ImportError:
    get_url = None

try:
    from social_django.models import UserSocialAuth
except ImportError:
    UserSocialAuth = None

# Only create manual enrollments if running in edx-platform
try:
    from common.djangoapps.student.api import (
        UNENROLLED_TO_ALLOWEDTOENROLL,
        UNENROLLED_TO_ENROLLED,
        create_manual_enrollment_audit,
    )
except ImportError:
    create_manual_enrollment_audit = None
    UNENROLLED_TO_ENROLLED = None
    UNENROLLED_TO_ALLOWEDTOENROLL = None


# For use with email templates
SELF_ENROLL_EMAIL_TEMPLATE_TYPE = 'SELF_ENROLL'
ADMIN_ENROLL_EMAIL_TEMPLATE_TYPE = 'ADMIN_ENROLL'

LOGGER = logging.getLogger(__name__)

User = auth.get_user_model()

try:
    from common.djangoapps.third_party_auth.provider import Registry
except ImportError as exception:
    LOGGER.warning("Could not import Registry from common.djangoapps.third_party_auth.provider")
    LOGGER.warning(exception)
    Registry = None

try:
    from common.djangoapps.track import segment
except ImportError as exception:
    LOGGER.warning("Could not import segment from common.djangoapps.track")
    LOGGER.warning(exception)
    segment = None

try:
    from openedx.core.djangoapps.user_api.models import UserPreference
except ImportError:
    UserPreference = None

try:
    from openedx.core.djangoapps.lang_pref import LANGUAGE_KEY
except ImportError:
    LANGUAGE_KEY = 'pref-lang'


class ValidationMessages:
    """
    Namespace class for validation messages.
    """

    # Keep this alphabetically sorted
    BOTH_FIELDS_SPECIFIED = _(
        "Either \"Email or Username\" or \"CSV bulk upload\" must be specified, "
        "but both were.")
    BULK_LINK_FAILED = _(
        "Error: Learners could not be added. Correct the following errors.")
    COURSE_MODE_INVALID_FOR_COURSE = _(
        "Enrollment track {course_mode} is not available for course {course_id}.")
    COURSE_WITHOUT_COURSE_MODE = _(
        "Select a course enrollment track for the given course(s).")
    INVALID_COURSE_ID = _(
        "Could not retrieve details for the course ID {course_id}. Specify "
        "a valid ID.")
    BOTH_COURSE_FIELDS_SPECIFIED = _(
        "Either \"CSV bulk upload\" or a singular course ID may be used for manual enrollments, "
        "but not both together."
    )
    INVALID_EMAIL = _(
        "{argument} does not appear to be a valid email address.")
    INVALID_EMAIL_OR_USERNAME = _(
        "{argument} does not appear to be a valid email address or known "
        "username")
    MISSING_EXPECTED_COLUMNS = _(
        "Expected a CSV file with [{expected_columns}] columns, but found "
        "[{actual_columns}] columns instead."
    )
    MISSING_REASON = _(
        "Reason field is required but was not filled."
    )
    NO_FIELDS_SPECIFIED = _(
        "Either \"Email or Username\" or \"CSV bulk upload\" must be "
        "specified, but neither were.")
    USER_ALREADY_REGISTERED = _(
        "User with email address {email} is already registered with Enterprise "
        "Customer {ec_name}")
    USER_NOT_LINKED = _("User is not linked with Enterprise Customer")
    USER_NOT_EXIST = _("User with email address {email} doesn't exist.")
    COURSE_NOT_EXIST_IN_CATALOG = _("Course ID {course_id} doesn't exist in Enterprise Customer's Catalog")
    INVALID_CHANNEL_WORKER = _(
        'Enterprise channel worker user with the username "{channel_worker_username}" was not found.'
    )
    INVALID_ENCODING = _(
        "Unable to parse CSV file. Please make sure it is a CSV 'utf-8' encoded file."
    )
    INVALID_DISCOUNT = _(
        'Discount percentage should be from 0 to 100.'
    )


class NotConnectedToOpenEdX(Exception):
    """
    Exception to raise when not connected to OpenEdX.

    In general, this exception shouldn't be raised, because this package is
    designed to be installed directly inside an existing OpenEdX platform.
    """

    def __init__(self, *args, **kwargs):
        """
        Log a warning and initialize the exception.
        """
        LOGGER.warning('edx-enterprise unexpectedly failed as if not installed in an OpenEdX platform')
        super().__init__(*args, **kwargs)


class CourseCatalogApiError(Exception):
    """
    Exception to raise when we we received data from Course Catalog but it contained an error.
    """


class CourseEnrollmentDowngradeError(Exception):
    """
    Exception to raise when an enrollment attempts to enroll the user in an unpaid mode when they are in a paid mode.
    """


class CourseEnrollmentPermissionError(Exception):
    """
    Exception to raise when an enterprise attempts to use enrollment features it's not configured to use.
    """


def get_social_auth_from_idp(idp, user=None, user_idp_id=None):
    """
    Return social auth entry of user for given enterprise IDP.

    idp (EnterpriseCustomerIdentityProvider): EnterpriseCustomerIdentityProvider Object
    user (User): User Object
    user_idp_id (str): User id of user in third party LMS
    """

    if idp:
        tpa_provider = get_identity_provider(idp.provider_id)
        filter_kwargs = {
            'provider': tpa_provider.backend_name,
            'uid__contains': tpa_provider.provider_id[5:]
        }
        if user_idp_id:
            provider_slug = tpa_provider.provider_id[5:]
            social_auth_uid = '{0}:{1}'.format(provider_slug, user_idp_id)
            filter_kwargs['uid'] = social_auth_uid
        else:
            filter_kwargs['user'] = user

        user_social_auth = UserSocialAuth.objects.select_related('user').filter(**filter_kwargs).first()

        return user_social_auth if user_social_auth else None

    return None


def get_user_valid_idp(user, enterprise_customer):
    """
    Return the default idp if it has user social auth record else it
    will return any idp with valid user social auth record

    user (User): user object
    enterprise_customer (EnterpriseCustomer): EnterpriseCustomer object
    """
    valid_identity_provider = None

    # If default idp provider has UserSocialAuth record then it has the highest priority.
    if get_social_auth_from_idp(enterprise_customer.default_provider_idp, user=user):
        valid_identity_provider = enterprise_customer.default_provider_idp
    else:
        for idp in enterprise_customer.identity_providers:
            if get_social_auth_from_idp(idp, user=user):
                valid_identity_provider = idp
                break
    return valid_identity_provider


def get_identity_provider(provider_id):
    """
    Get Identity Provider with given id.

    Return:
        Instance of ProviderConfig or None.
    """
    try:
        return Registry and Registry.get(provider_id)
    except ValueError:
        return None


def get_idp_choices():
    """
    Get a list of identity providers choices for enterprise customer.

    Return:
        A list of choices of all identity providers, None if it can not get any available identity provider.
    """

    first = [("", "-" * 7)]
    if Registry:
        return first + [(idp.provider_id, idp.name) for idp in Registry.enabled() if not idp.disable_for_enterprise_sso]
    return None


def get_all_field_names(model, excluded=None):
    """
    Return all fields' names from a model. Filter out the field names present in `excluded`.

    According to `Django documentation`_, ``get_all_field_names`` should become some monstrosity with chained
    iterable ternary nested in a list comprehension. For now, a simpler version of iterating over fields and
    getting their names work, but we might have to switch to full version in future.

    .. _Django documentation: https://docs.djangoproject.com/en/1.8/ref/models/meta/
    """
    excluded_fields = excluded or []
    return [f.name for f in model._meta.get_fields() if f.name not in excluded_fields]


def get_oauth2authentication_class():
    """
    Return oauth2 authentication class to authenticate REST APIs with Bearer token.
    """
    try:
        # pylint: disable=import-outside-toplevel
        from openedx.core.lib.api.authentication import OAuth2AuthenticationAllowInactiveUser as OAuth2Authentication
    except ImportError:
        return None

    return OAuth2Authentication


def get_catalog_admin_url(catalog_id):
    """
    Get url to catalog details admin page.

    Arguments:
        catalog_id (int): Catalog id for which to return catalog details url.

    Returns:
         URL pointing to catalog details admin page for the give catalog id.

    Example:
        >>> get_catalog_admin_url_template(2)
        "http://localhost:18381/admin/catalogs/catalog/2/change/"

    """
    return get_catalog_admin_url_template().format(catalog_id=catalog_id)


def get_catalog_admin_url_template(mode='change'):
    """
    Get template of catalog admin url.

    URL template will contain a placeholder '{catalog_id}' for catalog id.
    Arguments:
        mode e.g. change/add.

    Returns:
        A string containing template for catalog url.

    Example:
        >>> get_catalog_admin_url_template('change')
        "http://localhost:18381/admin/catalogs/catalog/{catalog_id}/change/"

    """
    api_base_url = getattr(settings, "COURSE_CATALOG_API_URL", "")

    # Extract FQDN (Fully Qualified Domain Name) from API URL.
    match = re.match(r"^(?P<fqdn>(?:https?://)?[^/]+)", api_base_url)

    if not match:
        return ""

    # Return matched FQDN from catalog api url appended with catalog admin path
    if mode == 'change':
        return match.group("fqdn").rstrip("/") + "/admin/catalogs/catalog/{catalog_id}/change/"
    if mode == 'add':
        return match.group("fqdn").rstrip("/") + "/admin/catalogs/catalog/add/"
    return None


def get_notification_subject_line(course_name, template_configuration=None):
    """
    Get a subject line for a notification email.

    The method is designed to fail in a "smart" way; if we can't render a
    database-backed subject line template, then we'll fall back to a template
    saved in the Django settings; if we can't render _that_ one, then we'll
    fall through to a friendly string written into the code.

    One example of a failure case in which we want to fall back to a stock template
    would be if a site admin entered a subject line string that contained a template
    tag that wasn't available, causing a KeyError to be raised.

    Arguments:
        course_name (str): Course name to be rendered into the string
        template_configuration: A database-backed object with a stored subject line template

    """
    stock_subject_template = _('You\'ve been enrolled in {course_name}!')
    default_subject_template = getattr(
        settings,
        'ENTERPRISE_ENROLLMENT_EMAIL_DEFAULT_SUBJECT_LINE',
        stock_subject_template,
    )
    if template_configuration is not None and template_configuration.subject_line:
        final_subject_template = template_configuration.subject_line
    else:
        final_subject_template = default_subject_template

    try:
        return final_subject_template.format(course_name=course_name)
    except KeyError:
        pass

    try:
        return default_subject_template.format(course_name=course_name)
    except KeyError:
        return stock_subject_template.format(course_name=course_name)


def find_enroll_email_template(enterprise_customer, template_type):
    """
    Find email template from the template database represented by EnrollmentNotificationEmailTemplate model.

    Arguments:
        - enterprise_customer (EnterpriseCustomer): the customer model
        - template_type (str): type of template to fetch, must be one of:
              enterprise.utils.SELF_ENROLL_EMAIL_TEMPLATE_TYPE, or
              enterprise.utils.ADMIN_ENROLL_EMAIL_TEMPLATE_TYPE

    Returns:
      Customer specific template if found.
      Default template for the given type if found.
      None if neither default template, nor per customer template found.
    """
    enrollment_template = apps.get_model('enterprise', 'EnrollmentNotificationEmailTemplate')

    if not enterprise_customer:
        raise ValueError('Must provide a enterprise_customer argument')

    if not template_type:
        raise ValueError('Must provide a template_type argument')

    # first try customer specific template for this type
    try:
        enterprise_template_config = enrollment_template.objects.filter(
            enterprise_customer=enterprise_customer,
            template_type=template_type,
        ).first()
    except (ObjectDoesNotExist, AttributeError):
        enterprise_template_config = None

    if not enterprise_template_config:
        # use the fallback template instead
        enterprise_template_config = enrollment_template.objects.filter(
            enterprise_customer=None,
            template_type=template_type,
        ).first()

    return enterprise_template_config


def is_pending_user(user):
    """
    Returns true if pending_user attributes are detected
    """
    return hasattr(user, 'user_email') and not hasattr(user, 'first_name')


def get_learner_portal_url(enterprise_customer):
    """
    Learner portal url for enterprise_customer
    """
    return get_configuration_value_for_site(
        enterprise_customer.site,
        'ENTERPRISE_LEARNER_PORTAL_BASE_URL',
        settings.ENTERPRISE_LEARNER_PORTAL_BASE_URL
    )


def serialize_notification_content(
    enterprise_customer,
    course_details,
    course_id,
    users,
    admin_enrollment=False,
    activation_links=None,
):
    """
    Prepare serializable contents to send emails with (if using tasks to send emails)

    Arguments:
    * enterprise_customer (enterprise.models.EnterpriseCustomer)
    * course_details (dict): With at least 'title', 'start' and 'course' keys
       (usually obtained via CourseCatalogApiClient)
    * course_id (str)
    * users (list): list of users to enroll (each user should be a User or PendingEnterpriseCustomerUser)
    * activation_links (dict): a dictionary map of unactivated license user emails to license activation links

    Returns: A list of dictionary objects that are of the form:
      {
        "user": user
        "enrolled_in": {
            'name': course_name,
            'url': destination_url,
            'type': 'course',
            'start': course_start,
        },
        "dashboard_url": dashboard_url,
        "enterprise_customer_uuid": self.uuid,
        "admin_enrollment": admin_enrollment,
      }
      where user is one of
          - 1: { 'first_name': name, 'username': user_name, 'email': email } (dict of User object)
          - 2: { 'user_email' : user_email } (dict of PendingEnterpriseCustomerUser object)
    """
    dashboard_url = None
    course_name = course_details.get('title')
    course_path = '/courses/{course_id}/course'.format(course_id=course_id)
    params = {}

    if admin_enrollment:
        dashboard_url = get_learner_portal_url(enterprise_customer)

    # add tpa_hint if there is only one IdP attached with enterprise_customer
    if enterprise_customer.has_single_idp:
        params = {'tpa_hint': enterprise_customer.identity_providers.first().provider_id}
    elif enterprise_customer.has_multiple_idps and enterprise_customer.default_provider_idp:
        params = {'tpa_hint': enterprise_customer.default_provider_idp.provider_id}
    course_path = urlquote("{}?{}".format(course_path, urlencode(params)))

    lms_root_url = get_configuration_value_for_site(
        enterprise_customer.site,
        'LMS_ROOT_URL',
        settings.LMS_ROOT_URL
    )

    try:
        course_start = parse_lms_api_datetime(course_details.get('start'))
    except (TypeError, ValueError):
        course_start = None
        LOGGER.exception(
            'None or empty value passed as course start date.\nCourse Details:\n{course_details}'.format(
                course_details=course_details,
            )
        )

    email_items = []
    for user in users:
        user_dict = model_to_dict(user, fields=['first_name', 'username', 'user_email', 'email'])
        if 'email' in user_dict:
            user_email = user_dict['email']
        elif 'user_email' in user_dict:
            user_email = user_dict['user_email']
        else:
            raise TypeError(_('`user` must have one of either `email` or `user_email`.'))
        login_or_register = 'register' if is_pending_user(user) else 'login'
        # if we have an activation link for a license, use that rather than the course URL
        if activation_links is not None and activation_links.get(user_email) is not None:
            destination_url = activation_links.get(user_email)
        else:
            destination_url = '{site}/{login_or_register}?next={course_path}'.format(
                site=lms_root_url,
                login_or_register=login_or_register,
                course_path=course_path
            )
        email_items.append({
            "user": user_dict,
            "enrolled_in": {
                'name': course_name,
                'url': destination_url,
                'type': 'course',
                'start': course_start,
            },
            "dashboard_url": dashboard_url,
            "enterprise_customer_uuid": enterprise_customer.uuid,
            "admin_enrollment": admin_enrollment,
        })
    return email_items


def send_email_notification_message(
        user,
        enrolled_in,
        dashboard_url,
        enterprise_customer_uuid,
        email_connection=None,
        admin_enrollment=False,
):
    """
    Send an email notifying a user about their enrollment in a course.

    Arguments:
        user: a dict with either of the following forms:
              - 1: { 'first_name': name, 'username': user_name, 'email': email } (similar to a User object)
              - 2: { 'user_email' : user_email } (similar to a PendingEnterpriseCustomerUser object)
        enrolled_in (dict): The dictionary contains details of the enrollable object
            (either course or program) that the user enrolled in. This MUST contain
            a `name` key, and MAY contain the other following keys:
                - url: A human-friendly link to the enrollable's home page
                - type: Either `course` or `program` at present
                - branding: A special name for what the enrollable "is"; for example,
                    "MicroMasters" would be the branding for a "MicroMasters Program"
                - start: A datetime object indicating when the enrollable will be available.
        dashboard_url: link to enterprise customer's unique homepage for user
        enterprise_customer_uuid: The EnterpriseCustomer uuid that the enrollment was created using.
        email_connection: An existing Django email connection that can be used without
            creating a new connection for each individual message
        admin_enrollment: If true, uses admin enrollment template instead of default ones.
    """
    if 'first_name' in user and 'username' in user:
        # PendingEnterpriseCustomerUsers don't have usernames or real names. We should
        # template slightly differently to make sure weird stuff doesn't happen.
        user_name = user['first_name']
        if not user_name:
            user_name = user['username']
    else:
        user_name = None

    # User-like dicts have an `email` attribute; PendingEnterpriseCustomerUser-like have `user_email`.
    if 'email' in user:
        user_email = user['email']
    elif 'user_email' in user:
        user_email = user['user_email']
    else:
        raise TypeError(_('`user` must have one of either `email` or `user_email`.'))

    enterprise_customer = get_enterprise_customer(enterprise_customer_uuid)
    msg_context = {
        'user_name': user_name,
        'enrolled_in': enrolled_in,
        'dashboard_url': dashboard_url,
        'organization_name': enterprise_customer.name,
    }

    if admin_enrollment:
        template_type = ADMIN_ENROLL_EMAIL_TEMPLATE_TYPE
    else:
        template_type = SELF_ENROLL_EMAIL_TEMPLATE_TYPE

    enterprise_template_config = find_enroll_email_template(enterprise_customer, template_type)

    if not enterprise_template_config:
        LOGGER.warning(
            'Cannot find email templates for %s, template_type: %s. '
            'Not sending notification email.',
            enterprise_customer.name, template_type
        )
        return None

    plain_msg, html_msg = enterprise_template_config.render_all_templates(msg_context)

    subject_line = get_notification_subject_line(enrolled_in['name'], enterprise_template_config)

    from_email_address = get_configuration_value_for_site(
        enterprise_customer.site,
        'DEFAULT_FROM_EMAIL',
        default=settings.DEFAULT_FROM_EMAIL
    )

    return mail.send_mail(
        subject_line,
        plain_msg,
        from_email_address,
        [user_email],
        html_message=html_msg,
        connection=email_connection
    )


def enterprise_customer_model():
    """
    Returns the ``EnterpriseCustomer`` class.
    """
    return apps.get_model('enterprise', 'EnterpriseCustomer')


def enterprise_enrollment_source_model():
    """
    Returns the ``EnterpriseEnrollmentSource`` class.
    """
    return apps.get_model('enterprise', 'EnterpriseEnrollmentSource')


def enterprise_customer_user_model():
    """
    Returns the ``EnterpriseCustomerUser`` class.
    """
    return apps.get_model('enterprise', 'EnterpriseCustomerUser')


def enterprise_course_enrollment_model():
    """
    Returns the ``EnterpriseCourseEnrollment`` class.
    """
    return apps.get_model('enterprise', 'EnterpriseCourseEnrollment')


def licensed_enterprise_course_enrollment_model():
    """
    returns the ``LicensedEnterpriseCourseEnrollment`` class.
    """
    return apps.get_model('enterprise', 'LicensedEnterpriseCourseEnrollment')


def enterprise_customer_invite_key_model():
    """
    Returns the ``EnterpriseCustomerInviteKey`` class.
    """
    return apps.get_model('enterprise', 'EnterpriseCustomerInviteKey')


def get_enterprise_customer(uuid):
    """
    Get the ``EnterpriseCustomer`` instance associated with ``uuid``.

    :param uuid: The universally unique ID of the enterprise customer.
    :return: The ``EnterpriseCustomer`` instance, or ``None`` if it doesn't exist.
    """
    EnterpriseCustomer = enterprise_customer_model()
    try:
        return EnterpriseCustomer.objects.get(uuid=uuid)
    except (EnterpriseCustomer.DoesNotExist, ValidationError):
        return None


def get_enterprise_uuids_for_user_and_course(auth_user, course_run_id, active=None):
    """
    Get the ``EnterpriseCustomer`` UUID(s) associated with a user and a course id``.

    Some users are associated with an enterprise customer via `EnterpriseCustomerUser` model,
        1. if given user is enrolled in a specific course via an enterprise customer enrollment,
           return related enterprise customers as a list.
        2. otherwise return empty list.

    Arguments:
        auth_user (contrib.auth.User): Django User
        course_run_id (str): Course Run to lookup an enrollment against.
        active: (boolean or None): Filter flag for returning active, inactive, or all uuids

    Returns:
        (list of str): enterprise customer uuids associated with the current user and course run or None

    """
    return enterprise_course_enrollment_model().get_enterprise_uuids_with_user_and_course(
        auth_user.id,
        course_run_id,
        active)


def get_enterprise_customer_for_user(auth_user):
    """
    Return first found enterprise customer instance for given user.

    Some users are associated with an enterprise customer via `EnterpriseCustomerUser` model,
        1. if given user is associated with any enterprise customer, return first enterprise customer.
        2. otherwise return `None`.

    Arguments:
        auth_user (contrib.auth.User): Django User

    Returns:
        (EnterpriseCustomer): enterprise customer associated with the current user.

    """
    EnterpriseCustomerUser = apps.get_model('enterprise', 'EnterpriseCustomerUser')
    try:
        return EnterpriseCustomerUser.objects.get(user_id=auth_user.id).enterprise_customer
    except EnterpriseCustomerUser.DoesNotExist:
        return None


def get_enterprise_customer_user(user_id, enterprise_uuid):
    """
    Return the object for EnterpriseCustomerUser.

    Arguments:
        user_id (str): user identifier
        enterprise_uuid (UUID): Universally unique identifier for the enterprise customer.

    Returns:
        (EnterpriseCustomerUser): enterprise customer user record

    """
    EnterpriseCustomerUser = apps.get_model('enterprise', 'EnterpriseCustomerUser')
    try:
        return EnterpriseCustomerUser.objects.get(
            enterprise_customer__uuid=enterprise_uuid,
            user_id=user_id
        )
    except EnterpriseCustomerUser.DoesNotExist:
        return None


def get_course_track_selection_url(course_run, query_parameters):
    """
    Return track selection url for the given course.

    Arguments:
        course_run (dict): A dictionary containing course run metadata.
        query_parameters (dict): A dictionary containing query parameters to be added to course selection url.

    Raises:
        (KeyError): Raised when course run dict does not have 'key' key.

    Returns:
        (str): Course track selection url.

    """
    try:
        course_root = reverse('course_modes_choose', kwargs={'course_id': course_run['key']})
    except KeyError:
        LOGGER.exception(
            "KeyError while parsing course run data.\nCourse Run: \n[%s]", course_run,
        )
        raise

    url = '{}{}'.format(
        settings.LMS_ROOT_URL,
        course_root
    )
    course_run_url = update_query_parameters(url, query_parameters)

    return course_run_url


def update_query_parameters(url, query_parameters):
    """
    Return url with updated query parameters.

    Arguments:
        url (str): Original url whose query parameters need to be updated.
        query_parameters (dict): A dictionary containing query parameters to be added to course selection url.

    Returns:
        (slug): slug identifier for the identity provider that can be used for identity verification of
            users associated the enterprise customer of the given user.

    """
    scheme, netloc, path, query_string, fragment = urlsplit(url)
    url_params = parse_qs(query_string)

    # Update url query parameters
    url_params.update(query_parameters)

    return urlunsplit(
        (scheme, netloc, path, urlencode(sorted(url_params.items()), doseq=True), fragment),
    )


def filter_audit_course_modes(enterprise_customer, course_modes):
    """
    Filter audit course modes out if the enterprise customer has not enabled the 'Enable audit enrollment' flag.

    Arguments:
        enterprise_customer: The EnterpriseCustomer that the enrollment was created using.
        course_modes: iterable with dictionaries containing a required 'mode' key

    """
    audit_modes = getattr(settings, 'ENTERPRISE_COURSE_ENROLLMENT_AUDIT_MODES', ['audit'])
    if not enterprise_customer.enable_audit_enrollment:
        return [course_mode for course_mode in course_modes if course_mode['mode'] not in audit_modes]
    return course_modes


def get_enterprise_customer_or_404(enterprise_uuid):
    """
    Given an EnterpriseCustomer UUID, return the corresponding EnterpriseCustomer or raise a 404.

    Arguments:
        enterprise_uuid (str): The UUID (in string form) of the EnterpriseCustomer to fetch.

    Returns:
        (EnterpriseCustomer): The EnterpriseCustomer given the UUID.

    """
    EnterpriseCustomer = enterprise_customer_model()
    try:
        enterprise_uuid = UUID(enterprise_uuid)
        return EnterpriseCustomer.objects.get(uuid=enterprise_uuid)
    except (TypeError, ValueError, EnterpriseCustomer.DoesNotExist) as no_customer_error:
        LOGGER.error('Unable to find enterprise customer for UUID: [%s]', enterprise_uuid)
        raise Http404 from no_customer_error


def get_enterprise_customer_by_slug_or_404(slug):
    """
    Given an EnterpriseCustomer slug, return the corresponding EnterpriseCustomer or raise a 404.

    Arguments:
        slug (str): The unique slug (a string) identifying the customer.

    Returns:
        (EnterpriseCustomer): The EnterpriseCustomer given the slug.
    """
    return get_object_or_404(
        enterprise_customer_model(),
        slug=slug,
    )


def get_enterprise_customer_by_invite_key_or_404(invite_key_uuid):
    """
    Given an EnterpriseCustomerInviteKey UUID, return the corresponding EnterpriseCustomer or raise a 404.

    Arguments:
        invite_key_uuid (str): The UUID identifying an EnterpriseCustomerInviteKey.

    Returns:
        (EnterpriseCustomer): The EnterpriseCustomer given the EnterpriseCustomerInviteKey UUID.
    """
    customer_invite_key = get_object_or_404(
        enterprise_customer_invite_key_model(),
        uuid=invite_key_uuid,
    )
    return customer_invite_key.enterprise_customer


def clean_html_for_template_rendering(text):
    """
    Given html text that will be rendered as a variable in a template, strip out characters that impact rendering.

    Arguments:
        text (str): The text to clean.

    Returns:
        (str): The cleaned text.
    """
    # Sometimes there are random new lines between tags that don't render nicely.
    return text.replace('>\\n<', '><')


def get_cache_key(**kwargs):
    """
    Wrapper method on edx_django_utils get_cache_key utility.
    """
    return get_django_cache_key(**kwargs)


def traverse_pagination(response, endpoint):
    """
    Traverse a paginated API response.

    Extracts and concatenates "results" (list of dict) returned by DRF-powered
    APIs.

    Arguments:
        response (Dict): Current response dict from service API
        endpoint (slumber Resource object): slumber Resource object from edx-rest-api-client

    Returns:
        list of dict.

    """
    results = response.get('results', [])

    next_page = response.get('next')
    while next_page:
        querystring = parse_qs(urlparse(next_page).query, keep_blank_values=True)
        response = endpoint.get(**querystring)
        results += response.get('results', [])
        next_page = response.get('next')

    return results


def ungettext_min_max(singular, plural, range_text, min_val, max_val):
    """
    Return grammatically correct, translated text based off of a minimum and maximum value.

    Example:
        min = 1, max = 1, singular = '{} hour required for this course', plural = '{} hours required for this course'
        output = '1 hour required for this course'

        min = 2, max = 2, singular = '{} hour required for this course', plural = '{} hours required for this course'
        output = '2 hours required for this course'

        min = 2, max = 4, range_text = '{}-{} hours required for this course'
        output = '2-4 hours required for this course'

        min = None, max = 2, plural = '{} hours required for this course'
        output = '2 hours required for this course'

    Expects ``range_text`` to already have a translation function called on it.

    Returns:
        ``None`` if both of the input values are ``None``.
        ``singular`` formatted if both are equal or one of the inputs, but not both, are ``None``, and the value is 1.
        ``plural`` formatted if both are equal or one of its inputs, but not both, are ``None``, and the value is > 1.
        ``range_text`` formatted if min != max and both are valid values.
    """
    if min_val is None and max_val is None:
        return None
    if min_val == max_val or min_val is None or max_val is None:
        # pylint: disable=translation-of-non-string
        return ungettext(singular, plural, min_val or max_val).format(min_val or max_val)
    return range_text.format(min_val, max_val)


def format_price(price, currency='$'):
    """
    Format the price to have the appropriate currency and digits..

    :param price: The price amount.
    :param currency: The currency for the price.
    :return: A formatted price string, i.e. '$10', '$10.52'.
    """
    if int(price) == price:
        return '{}{}'.format(currency, int(price))
    return '{}{:0.2f}'.format(currency, price)


def get_configuration_value_for_site(site, key, default=None):
    """
    Get the site configuration value for a key, unless a site configuration does not exist for that site.

    Useful for testing when no Site Configuration exists in edx-enterprise or if a site in LMS doesn't have
    a configuration tied to it.

    :param site: A Site model object
    :param key: The name of the value to retrieve
    :param default: The default response if there's no key in site config or settings
    :return: The value located at that key in the site configuration or settings file.
    """
    if hasattr(site, 'configuration'):
        return site.configuration.get_value(key, default)
    return default


def get_configuration_value(val_name, default=None, **kwargs):
    """
    Get a configuration value, or fall back to ``default`` if it doesn't exist.

    Also takes a `type` argument to guide which particular upstream method to use when trying to retrieve a value.
    Current types include:
        - `url` to specifically get a URL.
    """
    if kwargs.get('type') == 'url':
        return get_url(val_name) or default if callable(get_url) else default
    return configuration_helpers.get_value(val_name, default, **kwargs) if configuration_helpers else default


def get_request_value(request, key, default=None):
    """
    Get the value in the request, either through query parameters or posted data, from a key.

    :param request: The request from which the value should be gotten.
    :param key: The key to use to get the desired value.
    :param default: The backup value to use in case the input key cannot help us get the value.
    :return: The value we're looking for.
    """
    if request.method in ['GET', 'DELETE']:
        return request.query_params.get(key, request.data.get(key, default))
    return request.data.get(key, request.query_params.get(key, default))


def get_program_type_description(program_type):
    """
    Get the pre-set description associated with this program type.

    :param program_type: The type of the program. Should be one of:

    * "MicroMasters Certificate"
    * "Professional Certificate"
    * "XSeries Certificate"

    :return: The description associated with the program type. If none exists, then the empty string.
    """
    return PROGRAM_TYPE_DESCRIPTION.get(program_type, '')


def get_enterprise_utm_context(enterprise_customer):
    """
    Get the UTM context for the enterprise.
    """
    return {
        'utm_medium': 'enterprise',
        'utm_source': slugify(enterprise_customer.name)
    }


def track_event(user_id, event_name, properties):
    """
    Emit a track event to segment (and forwarded to GA) for some parts of the Enterprise workflows.
    """
    # Only call the endpoint if the import was successful.
    if segment:
        segment.track(user_id, event_name, properties)


def track_enrollment(pathway, user_id, course_run_id, url_path=None):
    """
    Emit a track event for enterprise course enrollment.
    """
    track_event(user_id, 'edx.bi.user.enterprise.onboarding', {
        'pathway': pathway,
        'url_path': url_path,
        'course_run_id': course_run_id,
    })


def track_enterprise_user_linked(user_id, enterprise_customer_key, enterprise_customer_id, created_new_ent_user):
    """
    Emit a track event when user is linked to an enterprise
    """
    track_event(user_id, 'edx.bi.user.enterprise.onboarding', {
        'pathway': 'enterprise-user-linked',
        'enterprise_customer_key': enterprise_customer_key,
        'enterprise_customer_id': enterprise_customer_id,
        'created_new_enterprise_user': created_new_ent_user,
    })


def parse_datetime_handle_invalid(datetime_value):
    """
    Return the parsed version of a datetime string. If the string is invalid, return None.
    """
    try:
        if not isinstance(datetime_value, datetime.datetime):
            datetime_value = parse_datetime(datetime_value)
        return datetime_value.replace(tzinfo=pytz.UTC)
    except TypeError:
        return None


def get_course_run_duration_info(course_run):
    """
    Return course run's duration(str) info.
    """
    duration_info = ''
    min_effort = course_run.get('min_effort')
    max_effort = course_run.get('max_effort')
    weeks_to_complete = course_run.get('weeks_to_complete')
    if min_effort and max_effort and weeks_to_complete:
        duration_info = "{min_effort}-{max_effort} hours a week for {weeks_to_complete} weeks. ".format(
            min_effort=str(min_effort),
            max_effort=str(max_effort),
            weeks_to_complete=str(weeks_to_complete)
        )
    return duration_info


def is_course_run_enrollable(course_run):
    """
    Return true if the course run is enrollable, false otherwise.

    We look for the following criteria:
    1. end date is greater than a reasonably-defined enrollment window, or undefined
       * reasonably-defined enrollment window is 1 day before course run end date
    2. enrollment_start is less than now, or undefined
    3. enrollment_end is greater than now, or undefined
    """
    # Check if the course run is unpublished (sometimes these sneak through)
    if not is_course_run_published(course_run):
        return False

    now = datetime.datetime.now(pytz.UTC)
    reasonable_enrollment_window = now + datetime.timedelta(days=1)
    end = parse_datetime_handle_invalid(course_run.get('end'))
    enrollment_start = parse_datetime_handle_invalid(course_run.get('enrollment_start'))
    enrollment_end = parse_datetime_handle_invalid(course_run.get('enrollment_end'))
    return (not end or end > reasonable_enrollment_window) and \
           (not enrollment_start or enrollment_start < now) and \
           (not enrollment_end or enrollment_end > now)


def is_course_run_available_for_enrollment(course_run):
    """
    Check if a course run is available for enrollment.
    """
    # If the course run is Archived, it's not available for enrollment
    if course_run['availability'] not in ['Current', 'Starting Soon', 'Upcoming']:
        return False

    # If the course run is not "enrollable", it's not available for enrollment
    if not is_course_run_enrollable(course_run):
        return False

    return True


def has_course_run_available_for_enrollment(course_runs):
    """
        Iterates over all course runs to check if there any course run that is available for enrollment.

    :param course_runs: list of course runs
    :returns True if found else false
    """
    for course_run in course_runs:
        if is_course_run_available_for_enrollment(course_run):
            return True
    return False


def get_last_course_run_end_date(course_runs):
    """
    Returns the end date of the course run that falls at the end.
    """
    latest_end_date = None
    if course_runs:
        try:
            latest_end_date = max(course_run.get('end') for course_run in course_runs if
                                  parse_datetime_handle_invalid(course_run.get('end')) is not None)
        except ValueError:
            latest_end_date = None
    return latest_end_date


def is_course_run_upgradeable(course_run):
    """
    Return true if the course run has a verified seat with an unexpired upgrade deadline, false otherwise.
    """
    now = datetime.datetime.now(pytz.UTC)
    for seat in course_run.get('seats', []):
        if seat.get('type') == 'verified':
            upgrade_deadline = parse_datetime_handle_invalid(seat.get('upgrade_deadline'))
            return not upgrade_deadline or upgrade_deadline > now
    return False


def is_course_run_published(course_run):
    """
    Return True if the course run's status value is "published".
    """
    if course_run:
        if course_run.get('status') == 'published':
            return True
    return False


def get_course_run_start(course_run, default=None):
    """
    Return the given course run's start date as a datetime.
    """
    return parse_datetime_handle_invalid(course_run.get('start')) or default


def get_closest_course_run(course_runs):
    """
    Return course run with start date closest to now.
    """
    if len(course_runs) == 1:
        return course_runs[0]

    now = datetime.datetime.now(pytz.UTC)
    # course runs with no start date should be considered last.
    never = now - datetime.timedelta(days=3650)
    return min(course_runs, key=lambda x: abs(get_course_run_start(x, never) - now))


def get_active_course_runs(course, users_all_enrolled_courses):
    """
    Return active course runs (user is enrolled in) of the given course.

    This function will return the course_runs of 'course' which have
    active enrollment by looking into 'users_all_enrolled_courses'
    """
    # User's all course_run ids in which he has enrolled.
    enrolled_course_run_ids = [
        enrolled_course_run['course_details']['course_id'] for enrolled_course_run in users_all_enrolled_courses
        if enrolled_course_run['is_active'] and enrolled_course_run.get('course_details')
    ]
    return [course_run for course_run in course['course_runs'] if course_run['key'] in enrolled_course_run_ids]


def is_course_run_about_to_end(current_course_run):
    """
    Return False if end - now > course run's weeks to complete otherwise True.
    """
    about_to_end = True
    now = datetime.datetime.now(pytz.UTC)
    if current_course_run:
        end_date = parse_datetime_handle_invalid(current_course_run.get('end'))
        weeks_to_complete = current_course_run.get('weeks_to_complete') or 0
        if end_date and (end_date - now).days > weeks_to_complete * 7:
            about_to_end = False
    return about_to_end


def get_current_course_run(course, users_active_course_runs):
    """
    Return the current course run on the following conditions.

    - If user has active course runs (already enrolled) then return course run with closest start date
    Otherwise it will check the following logic:
    - Course run is enrollable (see is_course_run_enrollable)
    - Course run has a verified seat and the upgrade deadline has not expired.
    - If no enrollable/upgradeable course runs, then select all the course runs.
    - After filtering the course runs checks whether the filtered course run is about to close or not
    if yes then return the next course run or the current one.
    """
    current_course_run = None
    filtered_course_runs = []
    all_course_runs = course['course_runs']

    if users_active_course_runs:
        current_course_run = get_closest_course_run(users_active_course_runs)
    else:
        for course_run in all_course_runs:
            if is_course_run_enrollable(course_run) and is_course_run_upgradeable(course_run):
                filtered_course_runs.append(course_run)

        if not filtered_course_runs:
            # Consider all published runs if there were not any enrollable/upgradeable ones.
            filtered_course_runs = [course_run for course_run in all_course_runs
                                    if course_run['status'] == 'published']

        if filtered_course_runs:
            current_course_runs = [
                course_run for course_run in filtered_course_runs if course_run['availability'] == 'Current'
            ]
            current_course_run = current_course_runs[0] if current_course_runs else None
            if is_course_run_about_to_end(current_course_run):
                starting_soon_course_runs = [
                    course_run for course_run in filtered_course_runs if course_run['availability'] == 'Starting Soon'
                ] or filtered_course_runs
                current_course_run = get_closest_course_run(starting_soon_course_runs)
    return current_course_run


def strip_html_tags(text, allowed_tags=None):
    """
    Strip all tags from a string except those tags provided in `allowed_tags` parameter.

    Args:
        text (str): string to strip html tags from
        allowed_tags (list): allowed list of html tags

    Returns: a string without html tags
    """
    if text is None:
        return None
    if allowed_tags is None:
        allowed_tags = ALLOWED_TAGS
    return bleach.clean(text, tags=allowed_tags, attributes=['id', 'class', 'style', 'href', 'title'], strip=True)


def get_content_metadata_item_id(content_metadata_item):
    """
    Return the unique identifier given a content metadata item dictionary.
    """
    if content_metadata_item['content_type'] == 'program':
        return content_metadata_item['uuid']
    return content_metadata_item['key']


def get_default_catalog_content_filter():
    """
    Return default enterprise customer catalog content filter.
    """
    return settings.ENTERPRISE_CUSTOMER_CATALOG_DEFAULT_CONTENT_FILTER or DEFAULT_CATALOG_CONTENT_FILTER


def get_language_code(language):
    """
    Return IETF language tag of given language name.

    - if language is not found in the language map then `en-US` is returned.

    Args:
        language (str): string language name

    Returns: a language tag (two-letter language code - two letter country code if applicable)
    """
    language_map = {
        "Afrikaans": "af",
        "Arabic": "ar-AE",
        "Belarusian": "be",
        "Bulgarian": "bg-BG",
        "Catalan": "ca",
        "Czech": "cs-CZ",
        "Danish": "da-DK",
        "German": "de-DE",
        "Greek": "el-GR",
        "English": "en-US",
        "Spanish": "es-ES",
        "Estonian": "et",
        "Basque (Basque)": "eu",
        "Farsi": "fa",
        "Finnish": "fi-FI",
        "French": "fr-FR",
        "Hebrew": "he-IL",
        "Hindi": "hi",
        "Croatian": "hr",
        "Hungarian": "hu-HU",
        "Indonesian": "id-ID",
        "Icelandic": "is",
        "Italian": "it-IT",
        "Japanese": "ja-JP",
        "Korean": "ko-KR",
        "Lithuanian": "lt-LT",
        "Malay": "ms-MY",
        "Maltese": "mt",
        "Dutch": "nl-NL",
        "Norwegian": "nb-NO",
        "Polish": "pl-PL",
        "Portuguese": "pt-BR",
        "Romanian": "ro-RO",
        "Russian": "ru-RU",
        "Sanskrit": "sa",
        "Sorbian": "sb",
        "Slovak": "sk-SK",
        "Slovenian": "sl-SI",
        "Swedish": "sv-SE",
        "Swahili": "sw",
        "Tamil": "ta",
        "Thai": "th-TH",
        "Turkish": "tr-TR",
        "Tsonga": "ts",
        "Tatar": "tt",
        "Ukrainian": "uk",
        "Urdu": "ur",
        "Uzbek": "uz-UZ",
        "Vietnamese": "vi",
        "Xhosa": "xh",
        "Yiddish": "yi",
        "Chinese - Mandarin": "zh-CMN",
        "Chinese - China": "zh-CN",
        "Chinese - Simplified": "zh-Hans",
        "Chinese - Traditional": "zh-Hant",
        "Chinese - Hong Kong SAR": "zh-HK",
        "Chinese - Macau SAR": "zh-MO",
        "Chinese - Singapore": "zh-SG",
        "Chinese - Taiwan": "zh-TW",
        "Zulu": "zu",
    }
    return language_map.get(language, "en-US")


def get_enterprise_worker_user():
    """
    Return the user object of enterprise worker user.
    """
    return _get_service_worker(settings.ENTERPRISE_SERVICE_WORKER_USERNAME)


def get_ecommerce_worker_user():
    """
    Return the user object of ecommerce worker user.
    """
    return _get_service_worker(settings.ECOMMERCE_SERVICE_WORKER_USERNAME)


def _get_service_worker(service_worker_username):
    """
    Retrieve the specified service worker object. If user cannot be found then returns None.
    """
    try:
        return User.objects.get(username=service_worker_username)
    except User.DoesNotExist:
        return None


def discovery_query_url(content_filter, html_format=True):
    """
    Return discovery url for preview.
    """
    if CatalogIntegration is None:
        raise NotConnectedToOpenEdX(
            _(
                'To get a CatalogIntegration object, this package must be '
                'installed in an Open edX environment.'
            )
        )
    discovery_root_url = CatalogIntegration.current().get_internal_api_url()
    disc_url = '{discovery_root_url}{search_all_endpoint}?{query_string}'.format(
        discovery_root_url=discovery_root_url,
        search_all_endpoint='search/all/',
        query_string=urlencode(content_filter, doseq=True)
    )
    if html_format:
        return format_html(
            '<a href="{url}" target="_blank">Preview</a>',
            url=disc_url
        )
    return disc_url


def delete_data_sharing_consent(course_id, customer_uuid, user_email):
    """
    Delete the DSC records from the DB for given learner, course and customer, also its cache.
    """
    # Deleting the DSC record.
    user = User.objects.get(email=user_email)
    enterprise_customer_user = get_enterprise_customer_user(user.id, customer_uuid)
    enterprise_customer_user.data_sharing_consent_records.filter(course_id=course_id).delete()

    # Deleting the DCS cache
    consent_cache_key = get_cache_key(type='data_sharing_consent_needed', user_id=user.id, course_id=course_id)
    TieredCache.delete_all_tiers(consent_cache_key)


def validate_email_to_link(email, enterprise_customer, raw_email=None, message_template=None, raise_exception=True):
    """
    Validate email to be linked to Enterprise Customer.

    Performs two checks:
        * Checks that email is valid
        * Checks that it is not already linked to the provided Enterprise Customer

    Arguments:
        email (str): user email to link
        enterprise_customer (EnterpriseCustomer): the enterprise customer to link the email to
        raw_email (str): raw value as it was passed by user - used in error message.
        message_template (str): Validation error template string.
        raise_exception (bool): whether to raise an exception when an email is invalidated

    Raises:
        ValidationError: if email is invalid or already linked to Enterprise Customer.

    Returns:
        bool: Whether or not there is an existing record with the same email address.
    """
    raw_email = raw_email if raw_email is not None else email
    message_template = message_template if message_template is not None else ValidationMessages.INVALID_EMAIL
    try:
        validate_email(email)
    except ValidationError as validation_error:
        raise ValidationError(message_template.format(argument=raw_email)) from validation_error

    existing_record = enterprise_customer_user_model().objects.get_link_by_email(email, enterprise_customer)
    if existing_record and raise_exception:
        raise ValidationError(ValidationMessages.USER_ALREADY_REGISTERED.format(
            email=email, ec_name=existing_record.enterprise_customer.name
        ))
    return existing_record or False


def get_idiff_list(list_a, list_b):
    """
    Returns a list containing lower case difference of list_b and list_a after case insensitive comparison.

    Args:
        list_a: list of strings
        list_b: list of string

    Returns:
        List of unique lower case strings computed by subtracting list_b from list_a.
    """
    lower_list_a = [element.lower() for element in list_a]
    lower_list_b = [element.lower() for element in list_b]
    return list(set(lower_list_a) - set(lower_list_b))


def get_users_by_email(emails):
    """
    Accept a list of emails, and separate them into users that exist on OpenEdX and users who don't.

    Args:
        emails: An iterable of email addresses to split between existing and nonexisting

    Returns:
        users: Queryset of users who exist in the OpenEdX platform and who were in the list of email addresses
        unregistered_emails: List of unique emails which were in the original list, but do not yet exist as users
    """
    users = User.objects.filter(email__in=emails)
    present_emails = users.values_list('email', flat=True)
    unregistered_emails = get_idiff_list(emails, present_emails)
    return users, unregistered_emails


def is_user_enrolled(user, course_id, course_mode, enrollment_client=None):
    """
    Query the enrollment API and determine if a learner is enrolled in a given course run track.

    Args:
        user: The user whose enrollment needs to be checked
        course_mode: The mode with which the enrollment should be checked
        course_id: course id of the course where enrollment should be checked.
        enrollment_client: An optional EnrollmentAPIClient if it's already been instantiated and should be passed in.

    Returns:
        Boolean: Whether or not enrollment exists

    """
    if not enrollment_client:
        from enterprise.api_client.lms import EnrollmentApiClient  # pylint: disable=import-outside-toplevel
        enrollment_client = EnrollmentApiClient()
    try:
        enrollments = enrollment_client.get_course_enrollment(user.username, course_id)
        if enrollments and course_mode == enrollments.get('mode'):
            return True
    except HttpClientError as exc:
        logging.error(
            'Error while checking enrollment status of user %(user)s: %(message)s',
            dict(user=user.username, message=str(exc))
        )
    except KeyError as exc:
        logging.warning(
            'Error while parsing enrollment data of user %(user)s: %(message)s',
            dict(user=user.username, message=str(exc))
        )
    return False


def enroll_user(enterprise_customer, user, course_mode, *course_ids, **kwargs):
    """
    Enroll a single user in any number of courses using a particular course mode.

    Args:
        enterprise_customer: The EnterpriseCustomer model object which is sponsoring the enrollment
        user: The user model object who needs to be enrolled in the course
        course_mode: The string representation of the mode with which the enrollment should be created
        *course_ids: An iterable containing any number of course IDs to eventually enroll the user in.
        kwargs: Should contain enrollment_client if it's already been instantiated and should be passed in.

    Returns:
        Boolean: Whether or not enrollment succeeded for all courses specified
    """
    enrollment_client = kwargs.pop('enrollment_client', None)
    if not enrollment_client:
        from enterprise.api_client.lms import EnrollmentApiClient  # pylint: disable=import-outside-toplevel
        enrollment_client = EnrollmentApiClient()
    enterprise_customer_user, __ = enterprise_customer_user_model().objects.get_or_create(
        enterprise_customer=enterprise_customer,
        user_id=user.id
    )
    succeeded = True
    for course_id in course_ids:
        try:
            enrollment_client.enroll_user_in_course(
                user.username,
                course_id,
                course_mode,
                enterprise_uuid=str(enterprise_customer_user.enterprise_customer.uuid)
            )
        except HttpClientError as exc:
            # Check if user is already enrolled then we should ignore exception
            if is_user_enrolled(user, course_id, course_mode):
                succeeded = True
            else:
                succeeded = False
                default_message = 'No error message provided'
                try:
                    error_message = json.loads(exc.content.decode()).get('message', default_message)
                except ValueError:
                    error_message = default_message
                logging.error(
                    'Error while enrolling user %(user)s: %(message)s',
                    dict(user=user.username, message=error_message)
                )
        if succeeded:
            __, created = enterprise_course_enrollment_model().objects.get_or_create(
                enterprise_customer_user=enterprise_customer_user,
                course_id=course_id,
                defaults={
                    'source': enterprise_enrollment_source_model().get_source(
                        enterprise_enrollment_source_model().MANUAL
                    )
                }
            )
            if created:
                track_enrollment('admin-enrollment', user.id, course_id)
    return succeeded


def customer_admin_enroll_user_with_status(
        enterprise_customer,
        user,
        course_mode,
        course_id,
        enrollment_source=None,
        license_uuid=None
):
    """
    For use with bulk enrollment, or any use case of admin enrolling a user

    Enroll a single user in a course using a particular course mode, indicating it's a
    customer_admin enrolling a user (such as bulk enrollment). Return a status based on whether the enrollment existed
    before attempting to enroll.

    TODO: The `enroll_user` function above, used by Django admin, for example, should also be
    rewired to use this new ability, but for now it still uses enrollment client.

    Args:
        enterprise_customer: The EnterpriseCustomer model object which is sponsoring the enrollment
        user: The user model object who needs to be enrolled in the course
        course_mode: The string representation of the mode with which the enrollment should be created
        course_id: An opaque course_id to enroll in
        enrollment_source: Source of enrollment, used for tracking enrollments
        license_uuid: UUID of associated license with the enrollment, used to create a mapping between licenses and
            enrollments

    Returns:
        succeeded (Boolean): Whether or not the enrollment succeeded for the course specified
        created (Boolean): Whether or not the enrollment existed prior to calling method
    """
    enterprise_customer_user, __ = enterprise_customer_user_model().objects.get_or_create(
        enterprise_customer=enterprise_customer,
        user_id=user.id
    )
    succeeded = False
    new_enrollment = False
    try:
        # enrolls a user in a course per LMS flow, but this method does not create enterprise records yet so we need to
        # create it immediately after calling lms_enroll_user_in_course. lms_enroll_user_in_course can return None if
        # Enrollment already exists, does not fail in this case.
        new_enrollment = lms_enroll_user_in_course(
            user.username,
            course_id,
            course_mode,
            enterprise_customer.uuid,
            is_active=True,
        )
        succeeded = True
    except (CourseEnrollmentError, CourseUserGroup.DoesNotExist) as error:
        logging.exception("Failed to enroll user %s in course %s", user.id, course_id, exc_info=error)
    if succeeded:
        # If we have a provided enrollment source, use that. Otherwise default to manual.
        if enrollment_source:
            source = enrollment_source
        else:
            source = enterprise_enrollment_source_model().get_source(
                enterprise_enrollment_source_model().MANUAL
            )

        obj, created = enterprise_course_enrollment_model().objects.get_or_create(
            enterprise_customer_user=enterprise_customer_user,
            course_id=course_id,
            defaults={
                'source': source
            }
        )
        if license_uuid:
            licensed_enterprise_course_enrollment_model().objects.get_or_create(
                license_uuid=license_uuid,
                enterprise_course_enrollment=obj,
            )
        if created:
            # Note: this tracking event only caters to bulk enrollment right now.
            track_enrollment(PATHWAY_CUSTOMER_ADMIN_ENROLLMENT, user.id, course_id)

    # If new_enrollment is None then the enrollment already existed
    created = bool(new_enrollment)
    return succeeded, created


def customer_admin_enroll_user(enterprise_customer, user, course_mode, course_id, enrollment_source=None):
    """
    For use with bulk enrollment, or any use case of admin enrolling a user

    Enroll a single user in a course using a particular course mode, indicating it's a
    customer_admin enrolling a user (such as bulk enrollment)

    Args:
        enterprise_customer: The EnterpriseCustomer model object which is sponsoring the enrollment
        user: The user model object who needs to be enrolled in the course
        course_mode: The string representation of the mode with which the enrollment should be created
        course_id: An opaque course_id to enroll in

    Returns:
        succeeded (Boolean): Whether or not enrollment succeeded for the course specified
    """
    succeeded, __ = customer_admin_enroll_user_with_status(
        enterprise_customer,
        user,
        course_mode,
        course_id,
        enrollment_source
    )
    return succeeded


def get_create_ent_enrollment(
        course_id,
        enterprise_customer_user,
        enterprise_enrollment_source,
        license_uuid=None,
):
    """
    Get or Create the Enterprise Course Enrollment.

    If ``license_uuid`` present, will also create a LicensedEnterpriseCourseEnrollment record.
    """
    if enterprise_enrollment_source is not None:
        source = enterprise_enrollment_source
    else:
        raise TypeError("Failed to create enterprise enrollment for {user} in course {course}: "
                        "Enterprise enrollment source is not defined".format(
                            user=enterprise_customer_user.user_id,
                            course=course_id,
                        )
                        )
    # Create the Enterprise backend database records for this course
    # enrollment
    enterprise_course_enrollment, created = enterprise_course_enrollment_model().objects.get_or_create(
        enterprise_customer_user=enterprise_customer_user,
        course_id=course_id,
        defaults={
            'source': source
        }
    )
    if license_uuid and not enterprise_course_enrollment.license:
        LOGGER.info(
            'LicensedEnterpriseCourseEnrollment being created with following info: '
            'License UUID: {license_uuid}, '
            'EnterpriseCourseEnrollment: {enterprise_course_enrollment_uuid}'.format(
                license_uuid=license_uuid,
                enterprise_course_enrollment_uuid=enterprise_course_enrollment,
            )
        )
        licensed_enterprise_course_enrollment_model().objects.create(
            license_uuid=license_uuid,
            enterprise_course_enrollment=enterprise_course_enrollment,
        )
    return enterprise_course_enrollment, created


def enroll_licensed_users_in_courses(enterprise_customer, licensed_users_info, discount=100.00):
    """
    Takes a list of licensed learner data and enrolls each learner in the requested courses.

    Args:
        - enterprise_customer: The EnterpriseCustomer (object) which is sponsoring the enrollment
        - licensed_users_info: (list) An array of dictionaries, each containing information necessary to create a
            licensed enterprise enrollment for a specific learner in a specified course run.
            Example:
                licensed_users_info: [
                    {
                        'email': 'newuser@test.com',
                        'course_run_key': 'course-v1:edX+DemoX+Demo_Course',
                        'course_mode': 'verified',
                        'license_uuid': '5b77bdbade7b4fcb838f8111b68e18ae'
                    }
                ]
        - discount: (int) the discount offered to the learner for their enrollment. Subscription based enrollments
            default to 100

    Expected Return Values:
        Results: {
            successes: [{ 'email': <email>, 'course_run_key': <key>, 'user': <user object> } ... ],
            pending: [{ 'email': <email>, 'course_run_key': <key>, 'user': <user object> } ... ],
            failures: [{ 'email': <email>, 'course_run_key': <key> } ... ]
        }
    """
    results = {
        'successes': [],
        'pending': [],
        'failures': [],
    }
    for licensed_user_info in licensed_users_info:
        user_email = licensed_user_info.get('email')
        course_mode = licensed_user_info.get('course_mode')
        course_run_key = licensed_user_info.get('course_run_key')
        license_uuid = licensed_user_info.get('license_uuid')
        activation_link = licensed_user_info.get('activation_link')

        user = User.objects.filter(email=licensed_user_info['email']).first()
        try:
            if user:
                enrollment_source = enterprise_enrollment_source_model().get_source(
                    enterprise_enrollment_source_model().CUSTOMER_ADMIN
                )
                succeeded, created = customer_admin_enroll_user_with_status(
                    enterprise_customer, user, course_mode, course_run_key, enrollment_source, license_uuid
                )
                if succeeded:
                    results['successes'].append({
                        'user': user,
                        'email': user_email,
                        'course_run_key': course_run_key,
                        'created': created,
                        'activation_link': activation_link,
                    })
                else:
                    results['failures'].append({'email': user_email, 'course_run_key': course_run_key})
            else:
                pending_user, new_enrollments = enterprise_customer.enroll_user_pending_registration_with_status(
                    user_email,
                    course_mode,
                    course_run_key,
                    enrollment_source=enterprise_enrollment_source_model().get_source(
                        enterprise_enrollment_source_model().CUSTOMER_ADMIN
                    ),
                    discount=discount,
                    license_uuid=license_uuid
                )
                results['pending'].append({
                    'user': pending_user,
                    'email': user_email,
                    'course_run_key': course_run_key,
                    'created': new_enrollments[course_run_key],
                    'activation_link': activation_link,
                })
        except utils.IntegrityError:
            results['failures'].append({'email': user_email, 'course_run_key': course_run_key})
            continue

    return results


def enroll_users_in_course(
        enterprise_customer,
        course_id,
        course_mode,
        emails,
        enrollment_requester=None,
        enrollment_reason=None,
        discount=0.0,
        sales_force_id=None,
):
    """
    Enroll existing users in a course, and create a pending enrollment for nonexisting users.

    Args:
        enterprise_customer: The EnterpriseCustomer which is sponsoring the enrollment
        course_id (str): The unique identifier of the course in which we're enrolling
        course_mode (str): The mode with which we're enrolling in the course
        emails: An iterable of email addresses which need to be enrolled
        enrollment_requester (User): Admin user who is requesting the enrollment.
        enrollment_reason (str): A reason for enrollment.
        discount (Decimal): Percentage discount for enrollment.
        sales_force_id (str): Salesforce opportunity id.

    Returns:
        successes: A list of users who were successfully enrolled in the course
        pending: A list of PendingEnterpriseCustomerUsers who were successfully linked and had
            pending enrollments created for them in the database
        failures: A list of users who could not be enrolled in the course
    """
    existing_users, unregistered_emails = get_users_by_email(emails)

    successes = []
    pending = []
    failures = []

    for user in existing_users:
        succeeded = enroll_user(enterprise_customer, user, course_mode, course_id)
        if succeeded:
            successes.append(user)
            if enrollment_requester and enrollment_reason:
                create_manual_enrollment_audit(
                    enrollment_requester,
                    user.email,
                    UNENROLLED_TO_ENROLLED,
                    enrollment_reason,
                    course_id,
                )
        else:
            failures.append(user)

    for email in unregistered_emails:
        pending_user = enterprise_customer.enroll_user_pending_registration(
            email,
            course_mode,
            course_id,
            enrollment_source=enterprise_enrollment_source_model().get_source(
                enterprise_enrollment_source_model().MANUAL
            ),
            discount=discount,
            sales_force_id=sales_force_id,
        )
        pending.append(pending_user)
        if enrollment_requester and enrollment_reason:
            create_manual_enrollment_audit(
                enrollment_requester,
                email,
                UNENROLLED_TO_ALLOWEDTOENROLL,
                enrollment_reason,
                course_id,
            )

    return successes, pending, failures


def is_valid_url(url):
    """
    Return where the specified URL is a valid absolute url.
    """
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False


def get_platform_logo_url():
    """
    Return an absolute URL of the platform logo using the branding api.
    """
    logo_url = get_logo_url() if get_logo_url else None
    if not logo_url:
        return None

    is_abs_url = is_valid_url(logo_url)
    if is_abs_url:
        return logo_url

    return urljoin(settings.LMS_ROOT_URL, logo_url)


def create_tableau_user(user_id, enterprise_customer_user):
    """
    Create the user in tableau and store the tableau user in the EnterpriseAnalyticsUser model.
    """
    from enterprise.models import EnterpriseAnalyticsUser  # pylint: disable=import-outside-toplevel
    tableau_auth, server = get_tableau_server()
    if tableau_auth and server and enterprise_customer_user:
        enterprise_uuid = enterprise_customer_user.enterprise_customer.uuid
        try:
            with server.auth.sign_in(tableau_auth):
                user_item = TSC.UserItem(user_id, TSC.UserItem.Roles.Viewer)
                user = server.users.add(user_item)
                LOGGER.info(
                    '[TABLEAU USER SYNC] Created user id: %s name: %s with '
                    'role: %s.', user.id, user.name, user.site_role,
                )
                EnterpriseAnalyticsUser.objects.get_or_create(
                    enterprise_customer_user=enterprise_customer_user,
                    analytics_user_id=user.id
                )
                add_user_to_tableau_group(user.id, str(enterprise_uuid))
        except ServerResponseError as exc:
            if not exc.code == '409017':
                LOGGER.error(
                    '[TABLEAU USER SYNC] Could not sync enterprise admin user %s in tableau.'
                    'Server returned: %s', user_id, str(exc),
                )
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.exception(
                '[TABLEAU USER SYNC] Could not sync enterprise admin user %s in tableau.'
                'Server returned: %s', user_id, str(exc),
            )
    else:
        LOGGER.warning(
            '[TABLEAU USER SYNC] Could not create user %s in tableau.',
            user_id,
        )


def get_tableau_server():
    """
    Return Tableau ServerAuth and Server instances or None
    """
    try:
        tableau_auth = TSC.TableauAuth(settings.TABLEAU_ADMIN_USER, settings.TABLEAU_ADMIN_USER_PASSWORD)
        server = TSC.Server(settings.TABLEAU_URL)
        server.use_server_version()
        return tableau_auth, server
    except AttributeError as err:
        LOGGER.error(
            '[TABLEAU USER SYNC] Could not sync enterprise admin user in tableau.'
            'Error detail: %s', str(err),
        )
        return None, None


def add_user_to_tableau_group(tableau_user_id, tableau_group):
    """
    Associate a user with the group in tableau. The function attempts to create the group, except when
    the server responds with an exception code of 409009, indicating that the group already
    exists. In the latter case, the user is associated with the existing group.
    """
    tableau_auth, server = get_tableau_server()
    if tableau_auth and server:
        try:
            with server.auth.sign_in(tableau_auth):
                group_to_create = TSC.GroupItem(tableau_group)
                group = server.groups.create(group_to_create)
                server.groups.add_user(group, tableau_user_id)
        except ServerResponseError as exc:
            if exc.code == '409009':  # Code returned by tableau server when group already exists
                try:
                    with server.auth.sign_in(tableau_auth):
                        enterprise_group = TSC.GroupItem(tableau_group)
                        server.groups.add_user(enterprise_group, tableau_user_id)
                except ServerResponseError as exc:
                    LOGGER.error(
                        '[TABLEAU USER SYNC] Could not associate user %s with group %s in tableau.'
                        'Server returned: %s', tableau_user_id, tableau_group, str(exc),
                    )
            else:
                raise
    else:
        LOGGER.warning(
            '[TABLEAU USER SYNC] Could not add tableau user %s to tableau group %s.',
            tableau_user_id,
            tableau_group,
        )


def delete_tableau_user(enterprise_customer_user):
    """
    Delete the user in Tableau.
    """
    from enterprise.models import EnterpriseAnalyticsUser  # pylint: disable=import-outside-toplevel
    enterprise_analytics_user = EnterpriseAnalyticsUser.objects.filter(
        enterprise_customer_user=enterprise_customer_user
    ).first()
    if enterprise_analytics_user:
        delete_tableau_user_by_id(enterprise_analytics_user.analytics_user_id)
    else:
        LOGGER.warning(
            '[TABLEAU USER SYNC] Could not find the associated tableau user id for enterprise customer user %s.',
            enterprise_customer_user.user_id,
        )


def delete_tableau_user_by_id(tableau_user_id):
    """
    Delete the user in Tableau.
    """
    tableau_auth, server = get_tableau_server()
    if tableau_user_id and tableau_auth and server:
        try:
            with server.auth.sign_in(tableau_auth):
                server.users.remove(tableau_user_id)
        except ServerResponseError as exc:
            LOGGER.info(
                '[TABLEAU USER SYNC] Could not delete enterprise admin user in Tableau.'
                'Server returned: %s', str(exc),
            )
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.exception(
                '[TABLEAU USER SYNC] Could not delete enterprise admin user in Tableau.'
                'Server returned: %s', str(exc),
            )
    else:
        LOGGER.warning(
            '[TABLEAU USER SYNC] Could not delete the Tableau user %s.',
            tableau_user_id,
        )


def unset_language_of_all_enterprise_learners(enterprise_customer):
    """
    Unset the language preference of all the learners belonging to the given enterprise customer.

    Arguments:
        enterprise_customer (EnterpriseCustomer): Instance of the enterprise customer.
    """
    if UserPreference:
        user_ids = list(enterprise_customer.enterprise_customer_users.values_list('user_id', flat=True))

        UserPreference.objects.filter(
            key=LANGUAGE_KEY,
            user_id__in=user_ids
        ).update(
            value=''
        )


def unset_enterprise_learner_language(enterprise_customer_user):
    """
    Unset the language preference of the given enterprise learners.

    Arguments:
        enterprise_customer_user (EnterpriseCustomerUser): Instance of the enterprise customer user.
    """
    if UserPreference:
        UserPreference.objects.update_or_create(
            key=LANGUAGE_KEY,
            user_id=enterprise_customer_user.user_id,
            defaults={'value': ''}
        )


def validate_course_exists_for_enterprise(enterprise_customer, course_id, **kwargs):
    """
    Validates that a specified course id exists within the LMS and within the enterprise_customer's catalog(s).

    Arguments:
        enterprise_customer (EnterpriseCustomer): Instance of the enterprise customer.
        course_id (string): The unique identifier of a course.
        kwargs: Should contain enrollment_client if it's already been instantiated and is passed in.
    """
    enrollment_client = kwargs.pop('enrollment_client', None)
    if not enrollment_client:
        from enterprise.api_client.lms import EnrollmentApiClient  # pylint: disable=import-outside-toplevel
        enrollment_client = EnrollmentApiClient()
    course_details = enrollment_client.get_course_details(course_id)
    if not course_details:
        raise ValidationError(ValidationMessages.INVALID_COURSE_ID.format(course_id=course_id))
    if not enterprise_customer.catalog_contains_course(course_id):
        raise ValidationError(ValidationMessages.COURSE_NOT_EXIST_IN_CATALOG.format(course_id=course_id))
    return course_details or False


def batch(iterable, batch_size=1):
    """
    Break up an iterable into equal-sized batches.

    Arguments:
        iterable (e.g. list): an iterable to batch
        batch_size (int): the size of each batch. Defaults to 1.
    Returns:
        generator: iterates through each batch of an iterable
    """
    if isinstance(iterable, QuerySet):
        iterable_len = iterable.count()
    else:
        iterable_len = len(iterable)
    for index in range(0, iterable_len, batch_size):
        yield iterable[index:min(index + batch_size, iterable_len)]


def get_best_mode_from_course_key(course_key):
    """
    Helper method to retrieve a list of enrollments for a given course and select the one most applicable to enroll an
    enterprise learner in.
    """
    course_modes = [mode.slug for mode in CourseMode.objects.filter(course_id=course_key)]
    best_course_mode = CourseModes.VERIFIED if CourseModes.VERIFIED in course_modes \
        else CourseModes.PROFESSIONAL if CourseModes.PROFESSIONAL in course_modes \
        else CourseModes.NO_ID_PROFESSIONAL if CourseModes.NO_ID_PROFESSIONAL in course_modes \
        else CourseModes.AUDIT

    return best_course_mode


def parse_lms_api_datetime(datetime_string, datetime_format=LMS_API_DATETIME_FORMAT):
    """
    Parse a received datetime into a timezone-aware, Python datetime object.

    Arguments:
        datetime_string: A string to be parsed.
        datetime_format: A datetime format string to be used for parsing

    """
    if isinstance(datetime_string, datetime.datetime):
        date_time = datetime_string
    else:
        try:
            date_time = datetime.datetime.strptime(datetime_string, datetime_format)
        except ValueError:
            date_time = datetime.datetime.strptime(datetime_string, LMS_API_DATETIME_FORMAT_WITHOUT_TIMEZONE)

    # If the datetime format didn't include a timezone, then set to UTC.
    # Note that if we're using the default LMS_API_DATETIME_FORMAT, it ends in 'Z',
    # which denotes UTC for ISO-8661.
    if date_time.tzinfo is None:
        date_time = date_time.replace(tzinfo=timezone.utc)
    return date_time


def localized_utcnow():
    """Helper function to return localized utcnow()."""
    return pytz.UTC.localize(datetime.datetime.utcnow())  # pylint: disable=no-value-for-parameter
