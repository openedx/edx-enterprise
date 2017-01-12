# -*- coding: utf-8 -*-
"""
Utility functions for enterprise app.
"""
from __future__ import absolute_import, unicode_literals

import logging
import os
import re
from functools import wraps

from django.apps import apps
from django.conf import settings
from django.core import mail
from django.core.exceptions import ObjectDoesNotExist
from django.template.loader import render_to_string
from django.utils.translation import ugettext as _

import enterprise
from enterprise.django_compatibility import reverse
from six.moves.urllib.parse import urlparse, urlunparse  # pylint: disable=import-error,wrong-import-order

try:
    from edxmako.paths import add_lookup
except ImportError:
    add_lookup = None

try:
    # Try to import identity provider registry if third_party_auth is present
    from third_party_auth.provider import Registry
except ImportError:
    Registry = None


LOGGER = logging.getLogger(__name__)


class NotConnectedToEdX(Exception):
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
        super(NotConnectedToEdX, self).__init__(*args, **kwargs)


class NotConnectedToOpenEdX(Exception):
    """
    Exception to raise when we weren't able to import needed resources.

    This is raised when we try to use the resources, rather than on
    import, so that during testing we can load the module
    and mock out the resources we need.
    """

    pass


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


class ConditionalEmailConnection(object):
    """
    Conditionally open an email connection as a context manager.
    """

    def __init__(self, open_conn=False):
        """
        Save the preference of whether to open a connection.

        Args:
            open_conn (bool): Whether the context manager should create and open an email
            connection when entering a `with` statement.
        """
        self.open_conn = open_conn
        self.conn = None

    def __enter__(self):
        """
        Create and open the mail connection if necessary.
        """
        if self.open_conn:
            self.conn = mail.get_connection()
            self.conn.open()
        return self.conn

    def __exit__(self, *excinfo):
        """
        Close the email connection if it was opened.
        """
        if self.conn:
            self.conn.close()


def get_identity_provider(provider_id):
    """
    Get Identity Provider with given id.

    Raises a ValueError if it third_party_auth app is not available.

    Return:
        Instance of ProviderConfig or None.
    """
    return Registry and Registry.get(provider_id)


def get_idp_choices():
    """
    Get a list of identity providers choices for enterprise customer.

    Return:
        A list of choices of all identity providers, None if it can not get any available identity provider.
    """
    first = [("", "-"*7)]
    if Registry:
        return first + [(idp.provider_id, idp.name) for idp in Registry.enabled()]
    else:
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


def disable_for_loaddata(signal_handler):
    """
    Decorator that turns off signal handlers when loading fixture data.

    Django docs instruct to avoid further changes to the DB if raw=True as it might not be in a consistent state.
    See https://docs.djangoproject.com/en/dev/ref/signals/#post-save
    """
    # http://stackoverflow.com/a/15625121/882918
    @wraps(signal_handler)
    def wrapper(*args, **kwargs):
        """
        Function wrapper.
        """
        if kwargs.get('raw', False):
            return
        signal_handler(*args, **kwargs)
    return wrapper


def null_decorator(func):
    """
    Decorator that does nothing to the wrapped function.

    If we're unable to import social.pipeline.partial, which is the case in our CI platform,
    we need to be able to wrap the function with something.
    """
    return func


def patch_mako_lookup():
    """
    Update the EdX Mako paths to point to our consent template.

    Do nothing if we're not connected to OpenEdX.
    """
    if add_lookup is None:
        return
    full_location = os.path.realpath(__file__)
    directory = os.path.dirname(full_location)
    template_location = os.path.join(directory, 'templates', 'enterprise')
    # Both add an item to the setting AND insert the lookup for immediate use
    settings.MAKO_TEMPLATES['main'].insert(0, template_location)
    add_lookup('main', template_location)


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


def get_catalog_admin_url_template():
    """
    Get template of catalog admin url.

    URL template will contain a placeholder '{catalog_id}' for catalog id.

    Returns:
        A string containing template for catalog url.

    Example:
        >>> get_catalog_admin_url_template()
        "http://localhost:18381/admin/catalogs/catalog/{catalog_id}/change/"
    """
    api_base_url = getattr(settings, "COURSE_CATALOG_API_URL", "")

    # Extract FQDN (Fully Qualified Domain Name) from API URL.
    match = re.match(r"^(?P<fqdn>(?:https?://)?[^/]+)", api_base_url)

    if not match:
        return ""

    # Return matched FQDN from catalog api url appended with catalog admin path
    return match.group("fqdn").rstrip("/") + "/admin/catalogs/catalog/{catalog_id}/change/"


def consent_necessary_for_course(user, course_id):
    """
    Determine if consent is necessary before a user can access a course they've enrolled in.

    Args:
        user: The user attempting to access the course
        course_id: The string ID of the course in question
    """
    # Get the model on demand, since we can't have a circular dependency
    EnterpriseCourseEnrollment = apps.get_model(  # pylint: disable=invalid-name
        app_label='enterprise',
        model_name='EnterpriseCourseEnrollment'
    )
    try:
        enrollment = EnterpriseCourseEnrollment.objects.get(
            enterprise_customer_user__user_id=user.id,
            course_id=course_id
        )
    except EnterpriseCourseEnrollment.DoesNotExist:
        return False
    return enrollment.consent_needed


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
        site_template_configuration = enterprise_customer.site.enterprise_enrollment_template
    except (ObjectDoesNotExist, AttributeError):
        site_template_configuration = None

    plain_msg, html_msg = build_notification_message(msg_context, site_template_configuration)

    subject_line = get_notification_subject_line(enrolled_in['name'], site_template_configuration)

    return mail.send_mail(
        subject_line,
        plain_msg,
        settings.DEFAULT_FROM_EMAIL,
        [user_email],
        html_message=html_msg,
        connection=email_connection
    )


def get_reversed_url_by_site(request, site, *args, **kwargs):
    """
    Get a function to do a standard Django `reverse`, and then apply that path to another site's domain.

    We use urlparse to split the url into its individual components, and then replace
    the netloc with the domain for the site in question. We then unparse the result
    into a URL string.

    Arguments:
        request: The Django request currently being processed
        site (site): The site we want to apply to the URL created
        *args: Pass to the standard reverse function
        **kwargs: Pass to the standard reverse function
    """
    domain = site.domain
    reversed_url = reverse(*args, **kwargs)
    full_url = request.build_absolute_uri(reversed_url)
    parsed = urlparse(full_url)
    final_url = urlunparse(
        parsed._replace(netloc=domain)
    )
    return final_url


def get_enterprise_branding_info_by_provider_id(identity_provider_id=None):  # pylint: disable=invalid-name
    """
    Return the EnterpriseCustomer branding information based on provider_id.

    Arguments:
        identity_provider_id: There is 1:1 relation b/w EnterpriseCustomer and Identity provider.

    Returns:
        EnterpriseCustomerBrandingConfiguration instance associated with the customer of given identity provider.
    """
    return enterprise.models.EnterpriseCustomerBrandingConfiguration.objects.filter(
        enterprise_customer__enterprise_customer_identity_provider__provider_id=identity_provider_id
    ).first()


def get_enterprise_branding_info_by_ec_uuid(ec_uuid=None):  # pylint: disable=invalid-name
    """
    Return the EnterpriseCustomer branding information based on enterprise customer uuid.

    Arguments:
        ec_uuid (UUID): a universally unique identifier for the enterprise customer.

    Returns:
        EnterpriseCustomerBrandingConfiguration instance associated with the given enterprise customer uuid.
    """
    return enterprise.models.EnterpriseCustomerBrandingConfiguration.objects.filter(
        enterprise_customer__uuid=ec_uuid
    ).first()
