# -*- coding: utf-8 -*-
"""
Utility functions for enterprise app.
"""
from __future__ import absolute_import, division, unicode_literals

import datetime
import hashlib
import logging
import re
from uuid import UUID

import analytics
import bleach
import pytz
from eventtracking import tracker
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from six import iteritems  # pylint: disable=ungrouped-imports
# pylint: disable=import-error,wrong-import-order,ungrouped-imports
from six.moves.urllib.parse import parse_qs, quote_plus, urlencode, urlparse, urlsplit, urlunsplit

from django.apps import apps
from django.conf import settings
from django.core import mail
from django.core.exceptions import ObjectDoesNotExist
from django.core.urlresolvers import reverse
from django.http import Http404
from django.template.loader import render_to_string
from django.utils.dateparse import parse_datetime
from django.utils.text import slugify
from django.utils.translation import ugettext as _
from django.utils.translation import ungettext

from enterprise.constants import ALLOWED_TAGS, DEFAULT_CATALOG_CONTENT_FILTER, PROGRAM_TYPE_DESCRIPTION

try:
    from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers
except ImportError:
    configuration_helpers = None

try:
    from lms.djangoapps.branding.api import get_url
except ImportError:
    get_url = None

LOGGER = logging.getLogger(__name__)

try:
    from third_party_auth.provider import Registry  # pylint: disable=unused-import
except ImportError as exception:
    LOGGER.warning("Could not import Registry from third_party_auth.provider")
    LOGGER.warning(exception)
    Registry = None


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
        super(NotConnectedToOpenEdX, self).__init__(*args, **kwargs)


class CourseCatalogApiError(Exception):
    """
    Exception to raise when we we received data from Course Catalog but it contained an error.
    """


class MultipleProgramMatchError(CourseCatalogApiError):
    """
    Exception to raise when Course Catalog api returned multiple programs, while single program was expected.
    """

    def __init__(self, programs_matched, *args, **kwargs):
        """
        Initialize :class:`MultipleProgramMatchError`.

        Arguments:
            programs_matched (int): number of programs matched where one  proram was expected.
            args (iterable): variable arguments
            kwargs (dict): keyword arguments
        """
        super(MultipleProgramMatchError, self).__init__(*args, **kwargs)
        self.programs_matched = programs_matched


class CourseEnrollmentDowngradeError(Exception):
    """
    Exception to raise when an enrollment attempts to enroll the user in an unpaid mode when they are in a paid mode.
    """


class CourseEnrollmentPermissionError(Exception):
    """
    Exception to raise when an enterprise attempts to use enrollment features it's not configured to use.
    """


def get_identity_provider(provider_id):
    """
    Get Identity Provider with given id.

    Return:
        Instance of ProviderConfig or None.
    """
    try:
        from third_party_auth.provider import Registry   # pylint: disable=redefined-outer-name
    except ImportError as exception:
        LOGGER.warning("Could not import Registry from third_party_auth.provider")
        LOGGER.warning(exception)
        Registry = None  # pylint: disable=redefined-outer-name

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
    try:
        from third_party_auth.provider import Registry   # pylint: disable=redefined-outer-name
    except ImportError as exception:
        LOGGER.warning("Could not import Registry from third_party_auth.provider")
        LOGGER.warning(exception)
        Registry = None  # pylint: disable=redefined-outer-name

    first = [("", "-"*7)]
    if Registry:
        return first + [(idp.provider_id, idp.name) for idp in Registry.enabled()]
    return None


def get_all_field_names(model):
    """
    Return all fields' names from a model.

    According to `Django documentation`_, ``get_all_field_names`` should become some monstrosity with chained
    iterable ternary nested in a list comprehension. For now, a simpler version of iterating over fields and
    getting their names work, but we might have to switch to full version in future.

    .. _Django documentation: https://docs.djangoproject.com/en/1.8/ref/models/meta/
    """
    return [f.name for f in model._meta.get_fields()]


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
    elif mode == 'add':
        return match.group("fqdn").rstrip("/") + "/admin/catalogs/catalog/add/"


def build_notification_message(template_context, template_configuration=None):
    """
    Create HTML and plaintext message bodies for a notification.

    We receive a context with data we can use to render, as well as an optional site
    template configration - if we don't get a template configuration, we'll use the
    standard, built-in template.

    Arguments:
        template_context (dict): A set of data to render
        template_configuration: A database-backed object with templates
            stored that can be used to render a notification.

    """
    if (
            template_configuration is not None and
            template_configuration.html_template and
            template_configuration.plaintext_template
    ):
        plain_msg, html_msg = template_configuration.render_all_templates(template_context)
    else:
        plain_msg = render_to_string(
            'enterprise/emails/user_notification.txt',
            template_context
        )
        html_msg = render_to_string(
            'enterprise/emails/user_notification.html',
            template_context
        )

    return plain_msg, html_msg


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


def send_email_notification_message(user, enrolled_in, enterprise_customer, email_connection=None):
    """
    Send an email notifying a user about their enrollment in a course.

    Arguments:
        user: Either a User object or a PendingEnterpriseCustomerUser that we can use
            to get details for the email
        enrolled_in (dict): The dictionary contains details of the enrollable object
            (either course or program) that the user enrolled in. This MUST contain
            a `name` key, and MAY contain the other following keys:
                - url: A human-friendly link to the enrollable's home page
                - type: Either `course` or `program` at present
                - branding: A special name for what the enrollable "is"; for example,
                    "MicroMasters" would be the branding for a "MicroMasters Program"
                - start: A datetime object indicating when the enrollable will be available.
        enterprise_customer: The EnterpriseCustomer that the enrollment was created using.
        email_connection: An existing Django email connection that can be used without
            creating a new connection for each individual message

    """
    if hasattr(user, 'first_name') and hasattr(user, 'username'):
        # PendingEnterpriseCustomerUsers don't have usernames or real names. We should
        # template slightly differently to make sure weird stuff doesn't happen.
        user_name = user.first_name
        if not user_name:
            user_name = user.username
    else:
        user_name = None

    # Users have an `email` attribute; PendingEnterpriseCustomerUsers have `user_email`.
    if hasattr(user, 'email'):
        user_email = user.email
    elif hasattr(user, 'user_email'):
        user_email = user.user_email
    else:
        raise TypeError(_('`user` must have one of either `email` or `user_email`.'))

    msg_context = {
        'user_name': user_name,
        'enrolled_in': enrolled_in,
        'organization_name': enterprise_customer.name,
    }
    try:
        enterprise_template_config = enterprise_customer.enterprise_enrollment_template
    except (ObjectDoesNotExist, AttributeError):
        enterprise_template_config = None

    plain_msg, html_msg = build_notification_message(msg_context, enterprise_template_config)

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


def get_enterprise_customer(uuid):
    """
    Get the ``EnterpriseCustomer`` instance associated with ``uuid``.

    :param uuid: The universally unique ID of the enterprise customer.
    :return: The ``EnterpriseCustomer`` instance, or ``None`` if it doesn't exist.
    """
    EnterpriseCustomer = apps.get_model('enterprise', 'EnterpriseCustomer')  # pylint: disable=invalid-name
    try:
        return EnterpriseCustomer.objects.get(uuid=uuid)  # pylint: disable=no-member
    except EnterpriseCustomer.DoesNotExist:
        return None


def get_enterprise_customer_for_user(auth_user):
    """
    Return enterprise customer instance for given user.

    Some users are associated with an enterprise customer via `EnterpriseCustomerUser` model,
        1. if given user is associated with any enterprise customer, return enterprise customer.
        2. otherwise return `None`.

    Arguments:
        auth_user (contrib.auth.User): Django User

    Returns:
        (EnterpriseCustomer): enterprise customer associated with the current user.

    """
    EnterpriseCustomerUser = apps.get_model('enterprise', 'EnterpriseCustomerUser')  # pylint: disable=invalid-name
    try:
        return EnterpriseCustomerUser.objects.get(user_id=auth_user.id).enterprise_customer  # pylint: disable=no-member
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
    EnterpriseCustomerUser = apps.get_model('enterprise', 'EnterpriseCustomerUser')  # pylint: disable=invalid-name
    try:
        return EnterpriseCustomerUser.objects.get(  # pylint: disable=no-member
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
    EnterpriseCustomer = apps.get_model('enterprise', 'EnterpriseCustomer')  # pylint: disable=invalid-name
    try:
        enterprise_uuid = UUID(enterprise_uuid)
        return EnterpriseCustomer.objects.get(uuid=enterprise_uuid)  # pylint: disable=no-member
    except (ValueError, EnterpriseCustomer.DoesNotExist):
        LOGGER.error('Unable to find enterprise customer for UUID: [%s]', enterprise_uuid)
        raise Http404


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
    Get MD5 encoded cache key for given arguments.

    Here is the format of key before MD5 encryption.
        key1:value1__key2:value2 ...

    Example:
        >>> get_cache_key(site_domain="example.com", resource="enterprise")
        # Here is key format for above call
        # "site_domain:example.com__resource:enterprise"
        a54349175618ff1659dee0978e3149ca

    Arguments:
        **kwargs: Key word arguments that need to be present in cache key.

    Returns:
         An MD5 encoded key uniquely identified by the key word arguments.
    """
    key = '__'.join(['{}:{}'.format(item, value) for item, value in iteritems(kwargs)])

    return hashlib.md5(key.encode('utf-8')).hexdigest()


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
    if settings.LMS_SEGMENT_KEY:
        tracking_context = tracker.get_tracker().resolve_context()
        analytics.track(user_id, event_name, properties, context={
            'ip': tracking_context.get('ip'),
            'Google Analytics': {
                'clientId': tracking_context.get('client_id')
            }
        })


def track_enrollment(pathway, user_id, course_run_id, url_path=None):
    """
    Emit a track event for enterprise course enrollment.
    """
    track_event(user_id, 'edx.bi.user.enterprise.onboarding', {
        'pathway': pathway,
        'url_path': url_path,
        'course_run_id': course_run_id,
    })


def parse_datetime_handle_invalid(datetime_value):
    """
    Return the parsed version of a datetime string. If the string is invalid, return None.
    """
    try:
        return parse_datetime(datetime_value).replace(tzinfo=pytz.UTC)
    except TypeError:
        return None


def is_course_run_enrollable(course_run):
    """
    Return true if the course run is enrollable, false otherwise.

    We look for the following criteria:
    - end is greater than now OR null
    - enrollment_start is less than now OR null
    - enrollment_end is greater than now OR null
    """
    now = datetime.datetime.now(pytz.UTC)
    end = parse_datetime_handle_invalid(course_run.get('end'))
    enrollment_start = parse_datetime_handle_invalid(course_run.get('enrollment_start'))
    enrollment_end = parse_datetime_handle_invalid(course_run.get('enrollment_end'))
    return (not end or end > now) and \
           (not enrollment_start or enrollment_start < now) and \
           (not enrollment_end or enrollment_end > now)


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


def get_course_run_start(course_run, default=None):
    """
    Return the given course run's start date as a datetime.
    """
    return parse_datetime_handle_invalid(course_run.get('start')) or default


def get_current_course_run(course):
    """
    Return the current course run.

    Current is defined as the following:
    - Course run is enrollable (see is_course_run_enrollable)
    - Course run has a verified seat and the upgrade deadline has not expired.
    - Course run start date is closer to now than any other enrollable/upgradeable course runs.
    - If no enrollable/upgradeable course runs, return course run with most recent start date.
    """
    now = datetime.datetime.now(pytz.UTC)
    never = now - datetime.timedelta(days=3650)
    all_course_runs = course['course_runs']
    filtered_course_runs = []

    for course_run in all_course_runs:
        if is_course_run_enrollable(course_run) and is_course_run_upgradeable(course_run):
            filtered_course_runs.append(course_run)

    if not filtered_course_runs:
        # Consider all runs if there were not any enrollable/upgradeable ones.
        filtered_course_runs = all_course_runs

    if filtered_course_runs:
        # Return course run with start date closest to now.
        # Course runs with a null start date should be considered last.
        return min(filtered_course_runs, key=lambda x: abs(get_course_run_start(x, never) - now))

    return None


def strip_html_tags(text, allowed_tags=None):
    """
    Strip all tags from a string except those tags provided in `allowed_tags` parameter.

    Args:
        text (str): string to strip html tags from
        allowed_tags (list): allowed list of html tags

    Returns: a string without html tags
    """
    if text is None:
        return
    if allowed_tags is None:
        allowed_tags = ALLOWED_TAGS
    return bleach.clean(text, tags=allowed_tags, attributes=['id', 'class', 'style', 'href', 'title'], strip=True)


def parse_course_key(course_identifier):
    """
    Return the serialized course key given either a course run ID or course key.
    """
    try:
        course_run_key = CourseKey.from_string(course_identifier)
    except InvalidKeyError:
        # Assume we already have a course key.
        return course_identifier

    return quote_plus(' '.join([course_run_key.org, course_run_key.course]))


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
