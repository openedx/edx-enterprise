"""
User-facing views for the Enterprise app.
"""

import datetime
import json
import re
from collections import namedtuple
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit, urlunsplit
from uuid import UUID

import pytz
import waffle  # pylint: disable=invalid-django-waffle-import
from dateutil.parser import parse
from edx_django_utils import monitoring
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from slumber.exceptions import HttpClientError

from django.apps import apps
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.db import IntegrityError, transaction
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.encoding import iri_to_uri
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.text import slugify
from django.utils.translation import get_language_from_request
from django.utils.translation import gettext as _
from django.utils.translation import ngettext
from django.views.generic import View
from django.views.generic.edit import FormView

from consent.helpers import get_data_sharing_consent
from consent.models import DataSharingConsent
from enterprise import constants, messages
from enterprise.api.v1.serializers import EnterpriseCustomerUserWriteSerializer
from enterprise.api_client.discovery import get_course_catalog_api_service_client
from enterprise.api_client.ecommerce import EcommerceApiClient
from enterprise.api_client.lms import EmbargoApiClient, EnrollmentApiClient
from enterprise.decorators import enterprise_login_required, force_fresh_session
from enterprise.forms import (
    ENTERPRISE_LOGIN_SUBTITLE,
    ENTERPRISE_LOGIN_TITLE,
    ENTERPRISE_SELECT_SUBTITLE,
    ERROR_MESSAGE_FOR_SLUG_LOGIN,
    EnterpriseLoginForm,
    EnterpriseSelectionForm,
)
from enterprise.logging import getEnterpriseLogger
from enterprise.models import (
    EnterpriseCourseEnrollment,
    EnterpriseCustomerCatalog,
    EnterpriseCustomerUser,
    EnterpriseEnrollmentSource,
)
from enterprise.utils import (
    CourseEnrollmentDowngradeError,
    CourseEnrollmentPermissionError,
    NotConnectedToOpenEdX,
    clean_html_for_template_rendering,
    filter_audit_course_modes,
    format_price,
    get_active_course_runs,
    get_best_mode_from_course_key,
    get_configuration_value,
    get_create_ent_enrollment,
    get_current_course_run,
    get_enterprise_customer_by_invite_key_or_404,
    get_enterprise_customer_by_slug_or_404,
    get_enterprise_customer_or_404,
    get_enterprise_customer_user,
    get_platform_logo_url,
    get_program_type_description,
    is_course_run_enrollable,
    localized_utcnow,
    track_enrollment,
    ungettext_min_max,
    update_query_parameters,
)
from integrated_channels.cornerstone.utils import create_cornerstone_learner_data

try:
    from openedx.core.djangoapps.catalog.utils import get_localized_price_text
except ImportError:
    get_localized_price_text = None

try:
    from openedx.core.djangoapps.programs.utils import ProgramDataExtender
except ImportError:
    ProgramDataExtender = None

try:
    from openedx.core.djangoapps.user_authn import cookies as user_authn_cookies
except ImportError:
    user_authn_cookies = None

try:
    from openedx.features.enterprise_support.utils import get_provider_login_url
except ImportError:
    get_provider_login_url = None

LOGGER = getEnterpriseLogger(__name__)
BASKET_URL = urljoin(settings.ECOMMERCE_PUBLIC_URL_ROOT, '/basket/add/')
LMS_DASHBOARD_URL = urljoin(settings.LMS_ROOT_URL, '/dashboard')
LMS_PROGRAMS_DASHBOARD_URL = urljoin(settings.LMS_ROOT_URL, '/dashboard/programs/{uuid}')
LMS_START_PREMIUM_COURSE_FLOW_URL = urljoin(settings.LMS_ROOT_URL, '/verify_student/start-flow/{course_id}/')
LMS_COURSEWARE_URL = urljoin(settings.LMS_ROOT_URL, '/courses/{course_id}/courseware')
LMS_REGISTER_URL = urljoin(settings.LMS_ROOT_URL, '/register')
ENTERPRISE_GENERAL_ERROR_PAGE = 'enterprise/enterprise_error_page_with_messages.html'

# Constants used for logging errors that occur during
# the Data-sharing consent flow
CATALOG_API_CONFIG_ERROR_CODE = 'ENTGDS004'
CUSTOMER_DOES_NOT_EXIST_ERROR_CODE = 'ENTGDS008'
CONTENT_ID_DOES_NOT_EXIST_ERROR_CODE = 'ENTGDS000'
LICENSED_ENROLLMENT_ERROR_CODE = 'ENTGDS100'
NO_CONSENT_RECORD_ERROR_CODE = 'ENTGDS0002'
REDIRECT_URLS_MISSING_ERROR_CODE = 'ENTGDS003'
COURSE_MODE_DOES_NOT_EXIST_ERROR_CODE = 'ENTHCE000'
ROUTER_VIEW_NO_COURSE_ID_ERROR_CODE = 'ENTRV000'
VERIFIED_MODE_UNAVAILABLE_ERROR_CODE = 'ENTGDS110'
ENROLLMENT_INTEGRITY_ERROR_CODE = 'ENTGDS009'

DSC_ERROR_MESSAGES_BY_CODE = {
    CATALOG_API_CONFIG_ERROR_CODE: 'Course catalog api configuration error.',
    CUSTOMER_DOES_NOT_EXIST_ERROR_CODE: 'No record found for Enterprise customer.',
    CONTENT_ID_DOES_NOT_EXIST_ERROR_CODE: 'The course or program with the given id does not exist.',
    LICENSED_ENROLLMENT_ERROR_CODE: 'Failed to enroll licensed learner into course.',
    NO_CONSENT_RECORD_ERROR_CODE: 'There is no consent record, or consent is not required.',
    REDIRECT_URLS_MISSING_ERROR_CODE: 'Required request values missing for action to be carried out.',
    COURSE_MODE_DOES_NOT_EXIST_ERROR_CODE: 'Course_modes for course not found.',
    ROUTER_VIEW_NO_COURSE_ID_ERROR_CODE: 'In Router View, could not find course run with given id.',
    VERIFIED_MODE_UNAVAILABLE_ERROR_CODE: 'The [verified] course mode is expired or otherwise unavailable',
    ENROLLMENT_INTEGRITY_ERROR_CODE: 'IntegrityError while creating EnterpriseCourseEnrollment.',
}


def _log_error_message(error_code, exception=None, logger_method=LOGGER.error, **kwargs):
    """
    Helper to log standardized error messages about DSC API failures.
    """
    error_message = DSC_ERROR_MESSAGES_BY_CODE[error_code]
    log_message = (
        '[Enterprise DSC API] {error_message} '
        'error_code: {error_code}, '
        'exception: {exception}'
    ).format(error_message=error_message, error_code=error_code, exception=exception)

    for key, value in kwargs.items():
        log_message += ', {key}: {value}'.format(key=key, value=value)

    logger_method(log_message)
    return log_message


# The query param used to indicate some reason for enrollment failure;
# added to the `failure_url` that can be redirected to during the
# DSC enrollment flow.
FAILED_ENROLLMENT_REASON_QUERY_PARAM = 'failure_reason'


class VerifiedModeUnavailableException(Exception):
    """
    Exception that indicates the verified enrollment mode
    has expired or is otherwise unavaible for a course run.
    """


FailedEnrollmentReason = namedtuple(
    'FailedEnrollmentReason',
    ['enrollment_client_error', 'failure_reason_message']
)


VERIFIED_MODE_UNAVAILABLE = FailedEnrollmentReason(
    enrollment_client_error='The [verified] course mode is expired or otherwise unavailable',
    failure_reason_message='verified_mode_unavailable',
)
DSC_DENIED = FailedEnrollmentReason(
    enrollment_client_error='Data Sharing Consent terms must be accepted in order to enroll',
    failure_reason_message='dsc_denied',
)


def get_safe_redirect_url(url, requires_https=None):
    """
    Ensure that the URL which is going to be used for redirection exists in whitelist.
    """
    redirect_whitelist = set(getattr(settings, 'LOGIN_REDIRECT_WHITELIST', []))
    if url_has_allowed_host_and_scheme(url, allowed_hosts=redirect_whitelist, require_https=requires_https):
        return iri_to_uri(url)
    return None


def verify_edx_resources():
    """
    Ensure that all necessary resources to render the view are present.
    """
    required_methods = {
        'ProgramDataExtender': ProgramDataExtender,
    }

    for key, method in required_methods.items():
        if method is None:
            raise NotConnectedToOpenEdX(
                _("The following method from the Open edX platform is necessary for this view but isn't available.")
                + "\nUnavailable: {method}".format(method=key)
            )


def get_global_context(request, enterprise_customer=None):
    """
    Get the set of variables that are needed by default across views.
    """
    platform_name = get_configuration_value("PLATFORM_NAME", settings.PLATFORM_NAME)
    context = {
        'enterprise_customer': enterprise_customer,
        'LMS_SEGMENT_KEY': settings.LMS_SEGMENT_KEY,
        'LANGUAGE_CODE': get_language_from_request(request),
        'tagline': get_configuration_value("ENTERPRISE_TAGLINE", settings.ENTERPRISE_TAGLINE),
        'platform_description': get_configuration_value(
            "PLATFORM_DESCRIPTION",
            settings.PLATFORM_DESCRIPTION,
        ),
        'LMS_ROOT_URL': settings.LMS_ROOT_URL,
        'platform_name': platform_name,
        'header_logo_alt_text': _('{platform_name} home page').format(platform_name=platform_name),
        'welcome_text': constants.WELCOME_TEXT.format(platform_name=platform_name),
        'logo_url': get_platform_logo_url(),
    }

    if enterprise_customer is not None:
        context.update({
            'enterprise_welcome_text': constants.ENTERPRISE_WELCOME_TEXT.format(
                enterprise_customer_name=enterprise_customer.name,
                platform_name=platform_name,
                strong_start='<strong>',
                strong_end='</strong>',
                line_break='<br/>',
                privacy_policy_link_start="<a href='{pp_url}' target='_blank'>".format(
                    pp_url=get_configuration_value('PRIVACY', 'https://www.edx.org/edx-privacy-policy', type='url'),
                ),
                privacy_policy_link_end="</a>",
            ),
        })

    return context


def get_price_text(price, request):
    """
    Return the localized converted price as string (ex. '$150 USD').

    If the local_currency switch is enabled and the users location has been determined this will convert the
    given price based on conversion rate from the Catalog service and return a localized string
    """
    if waffle.switch_is_active('local_currency') and get_localized_price_text:
        return get_localized_price_text(price, request)

    return format_price(price)


def render_page_with_error_code_message(request, context_data, error_code, exception=None, **kwargs):
    """
    Return a 404 page with specified error_code after logging error and adding message to django messages.
    """
    _log_error_message(error_code, exception=exception, **kwargs)
    messages.add_generic_error_message_with_code(request, error_code)
    return render(
        request,
        ENTERPRISE_GENERAL_ERROR_PAGE,
        context=context_data,
        status=404,
    )


def should_upgrade_to_licensed_enrollment(consent_record, license_uuid):
    """
    In the event that a learner did enroll into audit from B2C and they consented
    on the data sharing consent page, we want to upgrade their audit enrollment
    into verified when they view the course in the learner portal and hit
    the DSC GET endpoint again.
    """
    return consent_record is not None and consent_record.granted and license_uuid


def add_reason_to_failure_url(base_failure_url, failure_reason):
    """
    Adds a query param to the given ``base_failure_url`` indicating
    why an enrollment has failed.
    """
    (scheme, netloc, path, query, fragment) = list(urlsplit(base_failure_url))
    query_dict = parse_qs(query)
    query_dict[FAILED_ENROLLMENT_REASON_QUERY_PARAM] = failure_reason
    new_query = urlencode(query_dict, doseq=True)
    return urlunsplit((scheme, netloc, path, new_query, fragment))


class NonAtomicView(View):
    """
    A base class view for views that disable atomicity in requests.
    """

    @method_decorator(transaction.non_atomic_requests)
    def dispatch(self, request, *args, **kwargs):
        """
        Disable atomicity for the view.

        Since we have settings.ATOMIC_REQUESTS enabled, Django wraps all view functions in an atomic transaction, so
        they can be rolled back if anything fails.

        However, we need to be able to save data in the middle of get/post(), so that it's available for calls to
        external APIs.  To allow this, we need to disable atomicity at the top dispatch level.
        """
        return super().dispatch(request, *args, **kwargs)


class GrantDataSharingPermissions(View):
    """
    Provide a form and form handler for data sharing consent.

    View handles the case in which we get to the "verify consent" step, but consent
    hasn't yet been provided - this view contains a GET view that provides a form for
    consent to be provided, and a POST view that consumes said form.
    """
    preview_mode = False

    def course_or_program_exist(self, course_id, program_uuid):
        """
        Return whether the input course or program exist.
        """
        try:
            course_exists = course_id and get_course_catalog_api_service_client().get_course_id(course_id)
            program_exists = program_uuid and get_course_catalog_api_service_client().program_exists(program_uuid)
            return course_exists or program_exists
        except ImproperlyConfigured as exc:
            _log_error_message(
                CATALOG_API_CONFIG_ERROR_CODE, exception=exc, course_id=course_id, program_uuid=program_uuid,
            )
            return False

    def get_default_context(self, enterprise_customer, platform_name):
        """
        Get the set of variables that will populate the template by default.
        """
        context_data = {
            'page_title': _('Data sharing consent required'),
            'consent_message_header': _('Consent to share your data'),
            'requested_permissions_header': _(
                'Per the {start_link}Data Sharing Policy{end_link}, '
                '{bold_start}{enterprise_customer_name}{bold_end} would like to know about:'
            ).format(
                enterprise_customer_name=enterprise_customer.name,
                bold_start='<b>',
                bold_end='</b>',
                start_link='<a href="#consent-policy-dropdown-bar" '
                           'class="policy-dropdown-link background-input" id="policy-dropdown-link">',
                end_link='</a>',
            ),
            'agreement_text': _(
                'I agree to allow {platform_name} to share data about my enrollment, completion and performance in all '
                '{platform_name} courses and programs where my enrollment is sponsored by {enterprise_customer_name}.'
            ).format(
                enterprise_customer_name=enterprise_customer.name,
                platform_name=platform_name,
            ),
            'continue_text': _('Continue'),
            'abort_text': _('Decline and go back'),
            'policy_dropdown_header': _('Data Sharing Policy'),
            'sharable_items_header': _(
                'Enrollment, completion, and performance data that may be shared with {enterprise_customer_name} '
                '(or its designee) for these courses and programs are limited to the following:'
            ).format(
                enterprise_customer_name=enterprise_customer.name
            ),
            'sharable_items': [
                _(
                    'My email address for my {platform_name} account, '
                    'and the date when I created my {platform_name} account'
                ).format(
                    platform_name=platform_name
                ),
                _(
                    'My {platform_name} ID, and if I log in via single sign-on, '
                    'my {enterprise_customer_name} SSO user-ID'
                ).format(
                    platform_name=platform_name,
                    enterprise_customer_name=enterprise_customer.name,
                ),
                _('My {platform_name} username').format(platform_name=platform_name),
                _('My country or region of residence'),
                _(
                    'What courses and/or programs I\'ve enrolled in or unenrolled from, what track I '
                    'enrolled in (audit or verified) and the date when I enrolled in each course or program'
                ),
                _(
                    'Information about each course or program I\'ve enrolled in, '
                    'including its duration and level of effort required'
                ),
                _(
                    'Whether I completed specific parts of each course or program (for example, whether '
                    'I watched a given video or attempted or completed a given homework assignment)'
                ),
                _(
                    'My overall percentage completion of each course or program on a periodic basis, '
                    'including the total time spent in each course or program, the date when I last '
                    'logged in to each course or program and how much of the course or program content I have consumed'
                ),
                _('My performance in each course or program, including, for example, '
                  'my score on each assignment and current average of correct answers out of total attempted answers'),
                _('My final grade in each course or program, and the date when I completed each course or program'),
                _('Whether I received a certificate in each course or program'),
            ],
            'sharable_items_footer': _(
                'My permission applies only to data from courses or programs that are sponsored by '
                '{enterprise_customer_name}, and not to data from any {platform_name} courses or programs that '
                'I take on my own. I understand that I may withdraw my permission only by fully unenrolling '
                'from any courses or programs that are sponsored by {enterprise_customer_name}.'
            ).format(
                enterprise_customer_name=enterprise_customer.name,
                platform_name=platform_name,
            ),
            'sharable_items_note_header': _('Please note'),
            'sharable_items_notes': [
                _('If you decline to consent, that fact may be shared with {enterprise_customer_name}.').format(
                    enterprise_customer_name=enterprise_customer.name
                ),
                _(
                    'Any version of this Data Sharing Policy in a language other than English is provided '
                    'for convenience and you understand and agree that the English language version will '
                    'control if there is any conflict.'
                )
            ],
            'confirmation_modal_header': _('Are you sure you want to decline?'),
            'confirmation_modal_affirm_decline_text': _('I decline'),
            'confirmation_modal_abort_decline_text': _('View the data sharing policy'),
            'policy_link_template': _('View the {start_link}data sharing policy{end_link}.').format(
                start_link='<a href="#consent-policy-dropdown-bar" class="policy-dropdown-link background-input" '
                           'id="policy-dropdown-link">',
                end_link='</a>',
            ),
            'policy_return_link_text': _('Return to Top'),
        }
        return context_data

    def get_context_from_db(self, consent_page, platform_name, item, context):
        """
        Make set of variables(populated from db) that will be used in data sharing consent page.
        """
        enterprise_customer = consent_page.enterprise_customer
        course_title = context.get('course_title', None)
        course_start_date = context.get('course_start_date', None)
        context_data = {
            'text_override_available': True,
            'page_title': consent_page.page_title,
            'left_sidebar_text': consent_page.left_sidebar_text.format(
                enterprise_customer_name=enterprise_customer.name,
                platform_name=platform_name,
                item=item,
                course_title=course_title,
                course_start_date=course_start_date,
            ),
            'top_paragraph': consent_page.top_paragraph.format(
                enterprise_customer_name=enterprise_customer.name,
                platform_name=platform_name,
                item=item,
                course_title=course_title,
                course_start_date=course_start_date,
            ),
            'agreement_text': consent_page.agreement_text.format(
                enterprise_customer_name=enterprise_customer.name,
                platform_name=platform_name,
                item=item,
                course_title=course_title,
                course_start_date=course_start_date,
            ),
            'continue_text': consent_page.continue_text,
            'abort_text': consent_page.abort_text,
            'policy_dropdown_header': consent_page.policy_dropdown_header,
            'policy_paragraph': consent_page.policy_paragraph.format(
                enterprise_customer_name=enterprise_customer.name,
                platform_name=platform_name,
                item=item,
                course_title=course_title,
                course_start_date=course_start_date,
            ),
            'confirmation_modal_header': consent_page.confirmation_modal_header.format(
                enterprise_customer_name=enterprise_customer.name,
                platform_name=platform_name,
                item=item,
                course_title=course_title,
                course_start_date=course_start_date,
            ),
            'confirmation_alert_prompt': consent_page.confirmation_modal_text.format(
                enterprise_customer_name=enterprise_customer.name,
                platform_name=platform_name,
                item=item,
                course_title=course_title,
                course_start_date=course_start_date,
            ),
            'confirmation_modal_affirm_decline_text': consent_page.modal_affirm_decline_text,
            'confirmation_modal_abort_decline_text': consent_page.modal_abort_decline_text,
        }
        return context_data

    def is_course_run_id(self, course_id):
        """
        Returns True if the course_id is in the correct format of a course_run_id, false otherwise.

        Arguments:
            course_id (str): The course_key or course run id

        Returns:
            (Boolean): True or False
        """
        try:
            # Check if we have a course ID or a course run ID
            CourseKey.from_string(course_id)
        except InvalidKeyError:
            # The ID we have is for a course instead of a course run
            return False
        # If here, the course_id is a course_run_id
        return True

    def get_course_or_program_context(self, enterprise_customer, course_id=None, program_uuid=None):
        """
        Return a dict having course or program specific keys for data sharing consent page.
        """
        context_data = {}
        if course_id:
            context_data.update({'course_id': course_id, 'course_specific': True})
            if not self.preview_mode:
                try:
                    catalog_api_client = get_course_catalog_api_service_client(enterprise_customer.site)
                except ImproperlyConfigured as exc:
                    _log_error_message(
                        CATALOG_API_CONFIG_ERROR_CODE, exception=exc, course_id=course_id,
                        program_uuid=program_uuid, enterprise_customer_uuid=enterprise_customer.uuid,
                    )
                    raise Http404 from exc

                course_start_date = ''

                if self.is_course_run_id(course_id):
                    course_run_details = catalog_api_client.get_course_run(course_id)
                    if course_run_details['start']:
                        course_start_date = parse(course_run_details['start']).strftime('%B %d, %Y')
                    course_title = course_run_details['title']
                else:
                    course_details = catalog_api_client.get_course_details(course_id)
                    course_title = course_details.get('title')

                context_data.update({
                    'course_title': course_title,
                    'course_start_date': course_start_date,
                })
            else:
                context_data.update({
                    'course_title': 'Demo Course',
                    'course_start_date': datetime.datetime.now().strftime('%B %d, %Y'),
                })
        else:
            context_data.update({
                'program_uuid': program_uuid,
                'program_specific': True,
            })
        return context_data

    def get_page_language_context_data(
            self,
            course_id,
            enterprise_customer,
            success_url,
            failure_url,
            license_uuid,
            request,
            platform_name
    ):
        """
        Return a dict of data for the language on the page.
        """
        item = 'course' if course_id else 'program'
        # Translators: bold_start and bold_end are HTML tags for specifying enterprise name in bold text.
        context_data = {
            'consent_request_prompt': _(
                'To access this {item}, you must first consent to share your learning achievements '
                'with {bold_start}{enterprise_customer_name}{bold_end}. '
                'If you decline now, you will be redirected to the previous page.'
            ).format(
                enterprise_customer_name=enterprise_customer.name,
                bold_start='<b>',
                bold_end='</b>',
                item=item,
            ),
            'confirmation_alert_prompt': _(
                'To access this {item} and use your discount, you {bold_start}must{bold_end} consent '
                'to sharing your {item} data with {enterprise_customer_name}. '
                'If you decline now, you will be redirected to the previous page.'
            ).format(
                enterprise_customer_name=enterprise_customer.name,
                bold_start='<b>',
                bold_end='</b>',
                item=item,
            ),
            'redirect_url': success_url,
            'failure_url': failure_url,
            'defer_creation': request.GET.get('defer_creation') is not None,
            'license_uuid': license_uuid,
            'requested_permissions': [
                _('your enrollment in this {item}').format(item=item),
                _('your learning progress'),
                _('course completion'),
            ],
            'policy_link_template': '',
        }
        published_only = not self.preview_mode
        enterprise_consent_page = enterprise_customer.get_data_sharing_consent_text_overrides(
            published_only=published_only
        )
        if enterprise_consent_page:
            context_data.update(self.get_context_from_db(enterprise_consent_page, platform_name, item, context_data))
        else:
            context_data.update(self.get_default_context(enterprise_customer, platform_name))

        if request.GET.get('left_sidebar_text_override') is not None:
            # Allows sidebar text to be overridden by calling API
            context_data.update({'workflow_text_override_available': True,
                                 'workflow_left_sidebar_text': request.GET.get('left_sidebar_text_override')
                                 })

        return context_data

    @staticmethod
    def create_enterprise_course_enrollment(request, enterprise_customer, course_id, license_uuid=None):
        """Create EnterpriseCustomerUser and EnterpriseCourseEnrollment record if not already exists."""
        enterprise_customer_user, __ = EnterpriseCustomerUser.objects.update_or_create(
            enterprise_customer=enterprise_customer,
            user_id=request.user.id,
            defaults={'active': True},
        )
        enterprise_enrollment_source = EnterpriseEnrollmentSource.get_source(
            EnterpriseEnrollmentSource.ENROLLMENT_URL,
        )
        enterprise_customer_user.update_session(request)
        __, created = get_create_ent_enrollment(
            course_id,
            enterprise_customer_user,
            enterprise_enrollment_source,
            license_uuid=license_uuid,
        )
        if created:
            track_enrollment('data-consent-page-enrollment', request.user.id, course_id, request.path)

    def _enroll_learner_in_course(
            self,
            request,
            enterprise_customer,
            course_id,
            program_uuid,
            license_uuid
    ):
        """Enrolls an enterprise learner into a course."""
        # Create EnterpriseCourseEnrollment if we found course_run_id instead of course_key in course_id param.
        # Skip creating EnterpriseCourseEnrollment if we found course_key instead of course_run_id.

        # EnterpriseCourseEnrollment will be created when the user will select a course run.
        # A CourseEnrollment record will be created and on the post signal of the CourseEnrollment,
        # an EnterpriseCourseEnrollment record will also get created.
        if course_id and self.is_course_run_id(course_id):
            if license_uuid:
                enrollment_api_client = EnrollmentApiClient()
                existing_enrollment = enrollment_api_client.get_course_enrollment(
                    request.user.username, course_id
                )
                if (
                        not existing_enrollment or
                        existing_enrollment.get('mode') == constants.CourseModes.AUDIT or
                        existing_enrollment.get('is_active') is False
                ):
                    course_mode = get_best_mode_from_course_key(course_id)
                    LOGGER.info(
                        'Retrieved Course Mode: {course_modes} for Course {course_id}'.format(
                            course_id=course_id,
                            course_modes=course_mode
                        )
                    )
                    try:
                        enrollment_api_client.enroll_user_in_course(
                            request.user.username,
                            course_id,
                            course_mode
                        )
                        LOGGER.info(
                            'Created LMS enrollment for User {user} in Course {course_id} '
                            'with License {license_uuid} in Course Mode {course_mode}.'.format(
                                user=request.user.username,
                                course_id=course_id,
                                license_uuid=license_uuid,
                                course_mode=course_mode
                            )
                        )
                    except HttpClientError as exc:
                        monitoring.record_exception()

                        default_message = 'No error message provided'
                        try:
                            error_message = json.loads(exc.content.decode()).get('message', default_message)
                        except ValueError:
                            error_message = default_message
                        LOGGER.exception(
                            'Client Error while enrolling user %(user)s in %(course)s via enrollment API: %(message)s',
                            {
                                'user': request.user.username,
                                'course': course_id,
                                'message': error_message,
                            }
                        )
                        if VERIFIED_MODE_UNAVAILABLE.enrollment_client_error in error_message:
                            raise VerifiedModeUnavailableException(error_message) from exc
                        raise Exception(error_message) from exc
            try:
                self.create_enterprise_course_enrollment(request, enterprise_customer, course_id, license_uuid)
            except IntegrityError as exc:
                _log_error_message(
                    ENROLLMENT_INTEGRITY_ERROR_CODE, exception=exc,
                    course_id=course_id, program_uuid=program_uuid,
                    enterprise_customer_uuid=enterprise_customer.uuid,
                    user_id=request.user.id, license_uuid=license_uuid,
                )

    def _do_enrollment_and_redirect(
        self, request, enterprise_customer,
        course_id, program_uuid, license_uuid,
        success_url, failure_url, consent_record=None, consent_provided=True,
    ):
        """
        Helper to enroll a learner into a course, handle an expected error about
        verified course modes not being available, and return an appropriate
        redirect url.
        """
        error_message_kwargs = {
            'course_id': course_id,
            'program_uuid': program_uuid,
            'enterprise_customer_uuid': enterprise_customer.uuid,
            'user_id': request.user.id,
            'license_uuid': license_uuid,
        }
        try:
            self._enroll_learner_in_course(
                request=request,
                enterprise_customer=enterprise_customer,
                course_id=course_id,
                program_uuid=program_uuid,
                license_uuid=license_uuid,
            )
            if consent_record:
                consent_record.granted = consent_provided
                consent_record.save()
            return redirect(success_url)
        except VerifiedModeUnavailableException as exc:
            _log_error_message(
                error_code=VERIFIED_MODE_UNAVAILABLE_ERROR_CODE,
                exception=exc,
                **error_message_kwargs,
            )
            return redirect(
                add_reason_to_failure_url(
                    failure_url,
                    VERIFIED_MODE_UNAVAILABLE.failure_reason_message,
                )
            )
        except Exception as exc:  # pylint: disable=broad-except
            _log_error_message(
                error_code=LICENSED_ENROLLMENT_ERROR_CODE,
                exception=exc,
                **error_message_kwargs,
            )
            return redirect(failure_url)

    @method_decorator(login_required)
    def get(self, request):
        """
        Render a form to collect user input about data sharing consent.
        """
        enterprise_customer_uuid = request.GET.get('enterprise_customer_uuid')
        success_url = request.GET.get('next')
        failure_url = request.GET.get('failure_url')
        course_id = request.GET.get('course_id')
        program_uuid = request.GET.get('program_uuid', '')
        license_uuid = request.GET.get('license_uuid')
        self.preview_mode = bool(request.GET.get('preview_mode', False))
        source = request.GET.get('source', 'unknown')

        LOGGER.info(
            f'[ENTERPRISE CONSENT PAGE] Request received. Source: [{source}], User: [{request.user}], '
            f'Course: [{course_id}], Enterprise: [{enterprise_customer_uuid}]'
        )

        # Get enterprise_customer to start in case we need to render a custom 404 page
        # Then go through other business logic to determine (and potentially overwrite) the enterprise customer
        try:
            enterprise_customer = get_enterprise_customer_or_404(enterprise_customer_uuid)
        except Http404:
            _log_error_message(
                CUSTOMER_DOES_NOT_EXIST_ERROR_CODE, course_id=course_id, program_uuid=program_uuid,
                enterprise_customer_uuid=enterprise_customer_uuid, user_id=request.user.id,
            )
            raise

        context_data = get_global_context(request, enterprise_customer)

        if not self.preview_mode:
            if not self.course_or_program_exist(course_id, program_uuid):
                return render_page_with_error_code_message(
                    request, context_data, error_code=CONTENT_ID_DOES_NOT_EXIST_ERROR_CODE,
                    course_id=course_id, program_uuid=program_uuid,
                    enterprise_customer_uuid=enterprise_customer_uuid, user_id=request.user.id,
                )

            try:
                consent_record = get_data_sharing_consent(
                    request.user.username,
                    enterprise_customer_uuid,
                    program_uuid=program_uuid,
                    course_id=course_id
                )
                consent_required = consent_record.consent_required()
            except AttributeError:
                consent_required = None
            except ImproperlyConfigured as exc:
                return render_page_with_error_code_message(
                    request, context_data, error_code=CATALOG_API_CONFIG_ERROR_CODE, exception=exc,
                    course_id=course_id, program_uuid=program_uuid,
                    enterprise_customer_uuid=enterprise_customer_uuid, user_id=request.user.id
                )

            if (
                not enterprise_customer.requests_data_sharing_consent or
                should_upgrade_to_licensed_enrollment(consent_record, license_uuid)
            ):
                return self._do_enrollment_and_redirect(
                    request, enterprise_customer,
                    course_id, program_uuid, license_uuid,
                    success_url, failure_url,
                )

            if consent_record is None or not consent_required:
                _log_error_message(
                    NO_CONSENT_RECORD_ERROR_CODE, logger_method=LOGGER.info,
                    course_id=course_id, program_uuid=program_uuid, user_id=request.user.id,
                    enterprise_customer_uuid=enterprise_customer_uuid,
                    consent_record=consent_record, consent_required=consent_required,
                )
                redirect_url = success_url if success_url else LMS_DASHBOARD_URL
                return redirect(redirect_url)
            enterprise_customer = consent_record.enterprise_customer
        elif not request.user.is_staff:
            raise PermissionDenied()

        # Retrieve context data again now that enterprise_customer logic has been run
        context_data = get_global_context(request, enterprise_customer)

        if not (success_url and failure_url):
            return render_page_with_error_code_message(
                request, context_data, REDIRECT_URLS_MISSING_ERROR_CODE,
                course_id=course_id, enterprise_customer_uuid=enterprise_customer_uuid,
                user_id=request.user.id, success_url=success_url, failure_url=failure_url,
            )

        try:
            updated_context_dict = self.get_course_or_program_context(
                enterprise_customer,
                course_id=course_id,
                program_uuid=program_uuid
            )
            context_data.update(updated_context_dict)
        except Http404:
            return render_page_with_error_code_message(
                request, context_data, CATALOG_API_CONFIG_ERROR_CODE,
                course_id=course_id, program_uuid=program_uuid,
                enterprise_customer_uuid=enterprise_customer_uuid, user_id=request.user.id,
            )

        context_data.update(self.get_page_language_context_data(
            course_id=course_id,
            enterprise_customer=enterprise_customer,
            success_url=success_url,
            failure_url=failure_url,
            license_uuid=license_uuid,
            request=request,
            platform_name=context_data['platform_name'],
        ))

        return render(request, 'enterprise/grant_data_sharing_permissions.html', context=context_data)

    @method_decorator(login_required)
    def post(self, request):
        """
        Process the above form.
        """
        enterprise_customer_uuid = request.POST.get('enterprise_customer_uuid')
        success_url = request.POST.get('redirect_url')
        failure_url = request.POST.get('failure_url')
        course_id = request.POST.get('course_id', '')
        program_uuid = request.POST.get('program_uuid', '')
        license_uuid = request.POST.get('license_uuid')

        try:
            enterprise_customer = get_enterprise_customer_or_404(enterprise_customer_uuid)
        except Http404:
            _log_error_message(
                CUSTOMER_DOES_NOT_EXIST_ERROR_CODE, course_id=course_id, program_uuid=program_uuid,
                enterprise_customer_uuid=enterprise_customer_uuid, user_id=request.user.id,
            )
            raise

        context_data = get_global_context(request, enterprise_customer)

        success_url = get_safe_redirect_url(success_url)
        failure_url = get_safe_redirect_url(failure_url)
        if not (success_url and failure_url):
            return render_page_with_error_code_message(
                request, context_data, REDIRECT_URLS_MISSING_ERROR_CODE,
                course_id=course_id, enterprise_customer_uuid=enterprise_customer_uuid,
                user_id=request.user.id, success_url=success_url, failure_url=failure_url,
            )

        if not self.course_or_program_exist(course_id, program_uuid):
            return render_page_with_error_code_message(
                request, context_data, error_code=CONTENT_ID_DOES_NOT_EXIST_ERROR_CODE,
                course_id=course_id, program_uuid=program_uuid,
                enterprise_customer_uuid=enterprise_customer_uuid, user_id=request.user.id,
            )

        consent_record = get_data_sharing_consent(
            request.user.username,
            enterprise_customer_uuid,
            program_uuid=program_uuid,
            course_id=course_id
        )
        if consent_record is None:
            return render_page_with_error_code_message(
                request, context_data, error_code=NO_CONSENT_RECORD_ERROR_CODE,
                course_id=course_id, program_uuid=program_uuid,
                enterprise_customer_uuid=enterprise_customer_uuid, user_id=request.user.id
            )

        defer_creation = request.POST.get('defer_creation')
        consent_provided = bool(request.POST.get('data_sharing_consent', False))
        if defer_creation is None and consent_record.consent_required() and consent_provided:
            return self._do_enrollment_and_redirect(
                request, enterprise_customer,
                course_id, program_uuid, license_uuid,
                success_url, failure_url, consent_record=consent_record,
            )
        if consent_provided:
            return redirect(success_url)

        return redirect(
            add_reason_to_failure_url(
                failure_url,
                DSC_DENIED.failure_reason_message,
            )
        )


class EnterpriseLoginView(FormView):
    """
    Allow an enterprise learner to login by enterprise customer's slug login.
    """

    form_class = EnterpriseLoginForm
    template_name = 'enterprise/enterprise_customer_login_page.html'

    def get_context_data(self, **kwargs):
        """Return the context data needed to render the view."""
        context_data = super().get_context_data(**kwargs)
        context_data.update(get_global_context(self.request))
        context_data.update({
            'page_title': _('Enterprise Slug Login'),
            'enterprise_login_title_message': ENTERPRISE_LOGIN_TITLE,
            'enterprise_login_subtitle_message': ENTERPRISE_LOGIN_SUBTITLE,
        })
        return context_data

    def form_invalid(self, form):
        """
        If the form is invalid then return the errors.
        """
        # flatten the list of lists
        errors = [item for sublist in form.errors.values() for item in sublist]
        return JsonResponse({'errors': errors}, status=400)

    def form_valid(self, form):
        """
        If the form is valid, redirect to the third party auth login page.
        """
        # This case will only happened when we try to run the edx-enterprise independently.
        if not get_provider_login_url:
            return JsonResponse({'errors': [ERROR_MESSAGE_FOR_SLUG_LOGIN]}, status=400)

        return JsonResponse(
            {
                "url": get_provider_login_url(
                    self.request,
                    form.cleaned_data['provider_id'],
                )
            }
        )


class EnterpriseProxyLoginView(View):
    """
    Allows an enterprise learner to login via existing flow from the learner portal.
    """

    def get(self, request):
        """
        Redirects a learner through login with their enterprise's third party auth if it uses tpa.
        """
        redirect_to = LMS_REGISTER_URL
        (scheme, netloc, path, query, fragment) = list(urlsplit(redirect_to))
        query_dict = parse_qs(query)
        query_params = request.GET

        # Return 404 response if enterprise_slug not present or invalid
        enterprise_slug = query_params.get('enterprise_slug')
        enterprise_invite_key = query_params.get('enterprise_customer_invite_key')
        if not enterprise_slug and not enterprise_invite_key:
            raise Http404

        if enterprise_slug:
            enterprise_customer = get_enterprise_customer_by_slug_or_404(enterprise_slug)
        else:
            enterprise_customer = get_enterprise_customer_by_invite_key_or_404(enterprise_invite_key)

        # Add the next param to the redirect's query parameters
        next_param = query_params.get('next')
        if next_param:
            query_dict['next'] = next_param
        else:
            # Default redirect is to the Learner Portal for the given Enterprise
            learner_portal_base_url = get_configuration_value(
                'ENTERPRISE_LEARNER_PORTAL_BASE_URL',
                settings.ENTERPRISE_LEARNER_PORTAL_BASE_URL,
            )
            query_dict['next'] = f"{learner_portal_base_url}/{enterprise_customer.slug}"

        tpa_hint_param = query_params.get('tpa_hint')
        tpa_hint = enterprise_customer.get_tpa_hint(tpa_hint_param)

        if tpa_hint:
            # Add the tpa_hint to the redirect's 'next' query parameter
            # Redirect will be to the Enterprise Customer's TPA provider
            tpa_next_param = {
                'tpa_hint': tpa_hint,
            }
            query_dict['next'] = update_query_parameters(str(query_dict['next']), tpa_next_param)
        else:
            # If there's no linked IDP
            # Add Enterprise Customer UUID and proxy_login to the redirect's query parameters
            # Redirect will be to the edX Logistration with Enterprise Proxy Login sidebar
            query_dict['enterprise_customer'] = [str(enterprise_customer.uuid)]
            query_dict['proxy_login'] = [True]

        new_query = urlencode(query_dict, doseq=True)
        new_redirect_to = urlunsplit((scheme, netloc, path, new_query, fragment))
        return redirect(new_redirect_to)


@method_decorator(login_required, name='dispatch')
class EnterpriseSelectionView(FormView):
    """
    Allow an enterprise learner to activate one of learner's linked enterprises.
    """

    form_class = EnterpriseSelectionForm
    template_name = 'enterprise/enterprise_customer_select_form.html'

    def get_initial(self):
        """Return the initial data to use for forms on this view."""
        initial = super().get_initial()
        enterprises = EnterpriseCustomerUser.objects.filter(
            user_id=self.request.user.id
        ).values_list(
            'enterprise_customer__uuid', 'enterprise_customer__name'
        )
        initial.update({
            'enterprises': [(str(uuid), name) for uuid, name in enterprises],
            'success_url': get_safe_redirect_url(self.request.GET.get('success_url')),
            'user_id': self.request.user.id
        })
        LOGGER.info(
            '[Enterprise Selection Page] Request recieved. SuccessURL: %s',
            self.request.GET.get('success_url')
        )
        return initial

    def get_context_data(self, **kwargs):
        """Return the context data needed to render the view."""
        context_data = super().get_context_data(**kwargs)
        context_data.update(get_global_context(self.request))
        context_data.update({
            'page_title': _('Select Organization'),
            'select_enterprise_message_title': _('Select an organization'),
            'select_enterprise_message_subtitle': ENTERPRISE_SELECT_SUBTITLE,
        })
        return context_data

    def form_invalid(self, form):
        """
        If the form is invalid then return the errors.
        """
        # flatten the list of lists
        errors = [item for sublist in form.errors.values() for item in sublist]
        return JsonResponse({'errors': errors}, status=400)

    def form_valid(self, form):
        """
        If the form is valid, activate the selected enterprise.
        """
        enterprise_customer = form.cleaned_data['enterprise']
        serializer = EnterpriseCustomerUserWriteSerializer(data={
            'enterprise_customer': enterprise_customer,
            'username': self.request.user.username,
            'active': True
        })
        if serializer.is_valid():
            serializer.save()
            enterprise_customer_user = EnterpriseCustomerUser.objects.get(
                user_id=self.request.user.id,
                enterprise_customer=enterprise_customer
            )
            enterprise_customer_user.update_session(self.request)
            LOGGER.info(
                '[Enterprise Selection Page] Learner activated an enterprise. User: %s, EnterpriseCustomer: %s',
                self.request.user.username,
                enterprise_customer,
            )
            response = JsonResponse({})
            return user_authn_cookies.set_logged_in_cookies(
                self.request, response, self.request.user
            ) if user_authn_cookies else response

        return None


class HandleConsentEnrollment(View):
    """
    Handle enterprise course enrollment at providing data sharing consent.

    View handles the case for enterprise course enrollment after successful
    consent.
    """

    @method_decorator(enterprise_login_required)
    def get(self, request, enterprise_uuid, course_id):
        """
        Handle the enrollment of enterprise learner in the provided course.

        Based on `enterprise_uuid` in URL, the view will decide which
        enterprise customer's course enrollment record should be created.

        Depending on the value of query parameter `course_mode` then learner
        will be either redirected to LMS dashboard for audit modes or
        redirected to ecommerce basket flow for payment of premium modes.
        """
        enrollment_course_mode = request.GET.get('course_mode')
        enterprise_catalog_uuid = request.GET.get('catalog')

        # Redirect the learner to LMS dashboard in case no course mode is
        # provided as query parameter `course_mode`
        if not enrollment_course_mode:
            return redirect(LMS_DASHBOARD_URL)

        enrollment_api_client = EnrollmentApiClient()
        course_modes = enrollment_api_client.get_course_modes(course_id)

        # Verify that the request user belongs to the enterprise against the
        # provided `enterprise_uuid`.
        enterprise_customer = get_enterprise_customer_or_404(enterprise_uuid)
        enterprise_customer_user = get_enterprise_customer_user(request.user.id, enterprise_customer.uuid)
        enterprise_enrollment_source = EnterpriseEnrollmentSource.get_source(
            EnterpriseEnrollmentSource.ENROLLMENT_URL)

        if not course_modes:
            context_data = get_global_context(request, enterprise_customer)
            return render_page_with_error_code_message(
                request, context_data, error_code=COURSE_MODE_DOES_NOT_EXIST_ERROR_CODE,
                user_id=request.user.id, enterprise_catalog_uuid=enterprise_catalog_uuid,
                course_id=course_id,
            )

        selected_course_mode = None
        for course_mode in course_modes:
            if course_mode['slug'] == enrollment_course_mode:
                selected_course_mode = course_mode
                break

        if not selected_course_mode:
            return redirect(LMS_DASHBOARD_URL)

        # Create the Enterprise backend database records for this course
        # enrollment
        __, created = get_create_ent_enrollment(
            course_id,
            enterprise_customer_user,
            enterprise_enrollment_source
        )
        if created:
            track_enrollment('course-landing-page-enrollment', request.user.id, course_id, request.get_full_path())

        DataSharingConsent.objects.update_or_create(
            username=enterprise_customer_user.username,
            course_id=course_id,
            enterprise_customer=enterprise_customer_user.enterprise_customer,
            defaults={
                'granted': True
            },
        )

        audit_modes = getattr(
            settings,
            'ENTERPRISE_COURSE_ENROLLMENT_AUDIT_MODES',
            [constants.CourseModes.AUDIT, constants.CourseModes.HONOR]
        )
        if selected_course_mode['slug'] in audit_modes:
            # In case of Audit course modes enroll the learner directly through
            # enrollment API client and redirect the learner to dashboard.
            enrollment_api_client.enroll_user_in_course(
                request.user.username,
                course_id,
                selected_course_mode['slug'],
                enterprise_uuid=str(enterprise_customer_user.enterprise_customer.uuid)
            )

            return redirect(LMS_COURSEWARE_URL.format(course_id=course_id))

        # redirect the enterprise learner to the ecommerce flow in LMS
        # Note: LMS start flow automatically detects the paid mode
        premium_flow = LMS_START_PREMIUM_COURSE_FLOW_URL.format(course_id=course_id)
        if enterprise_catalog_uuid:
            premium_flow += '?catalog={catalog_uuid}'.format(
                catalog_uuid=enterprise_catalog_uuid
            )

        return redirect(premium_flow)


class CourseEnrollmentView(NonAtomicView):
    """
    Enterprise landing page view.

    This view will display the course mode selection with related enterprise
    information.
    """

    PACING_FORMAT = {
        'instructor_paced': _('Instructor-Paced'),
        'self_paced': _('Self-Paced')
    }

    def set_final_prices(self, modes, request):
        """
        Set the final discounted price on each premium mode.
        """
        result = []
        for mode in modes:
            if mode['premium']:
                mode['final_price'] = EcommerceApiClient(request.user).get_course_final_price(
                    mode=mode,
                    enterprise_catalog_uuid=request.GET.get(
                        'catalog'
                    ) if request.method == 'GET' else None,
                )
            result.append(mode)
        return result

    def get_available_course_modes(self, request, course_run_id, enterprise_catalog):
        """
        Return the available course modes for the course run.

        The provided EnterpriseCustomerCatalog is used to filter and order the
        course modes returned using the EnterpriseCustomerCatalog's
        field "enabled_course_modes".
        """
        modes = EnrollmentApiClient().get_course_modes(course_run_id)
        if not modes:
            error_code = 'ENTCEV000'
            LOGGER.warning(
                '[Enterprise Enrollment] Unable to get course modes. '
                'ErrorCode: {error_code}, '
                'CourseRun: {course_run_id}, '
                'Username: {username}, '
                'EnterpruseCatalog: {enterprise_catalog}'.format(
                    error_code=error_code,
                    course_run_id=course_run_id,
                    username=request.user.username,
                    enterprise_catalog=enterprise_catalog,
                )
            )
            messages.add_generic_error_message_with_code(request, error_code)

        if enterprise_catalog:
            # filter and order course modes according to the enterprise catalog
            modes = [mode for mode in modes if mode['slug'] in enterprise_catalog.enabled_course_modes]
            modes.sort(key=lambda course_mode: enterprise_catalog.enabled_course_modes.index(course_mode['slug']))
            if not modes:
                error_code = 'ENTCEV001'
                LOGGER.info(
                    '[Enterprise Enrollment] Matching course modes were not found in EnterpriseCustomerCatalog. '
                    'ErrorCode: {error_code}, '
                    'CourseRun: {course_run_id}, '
                    'Username: {username}, '
                    'EnterpriseCatalog: {enterprise_catalog_uuid}'.format(
                        error_code=error_code,
                        course_run_id=course_run_id,
                        username=request.user.username,
                        enterprise_catalog_uuid=enterprise_catalog,
                    )
                )
                messages.add_generic_error_message_with_code(request, error_code)

        return modes

    def get_base_details(self, request, enterprise_uuid, course_run_id):
        """
        Retrieve fundamental details used by both POST and GET versions of this view.

        Specifically, take an EnterpriseCustomer UUID and a course run ID, and transform those
        into an actual EnterpriseCustomer, a set of details about the course, and a list
        of the available course modes for that course run.
        """
        enterprise_customer = get_enterprise_customer_or_404(enterprise_uuid)

        # If the catalog query parameter was provided, we need to scope
        # this request to the specified EnterpriseCustomerCatalog.
        enterprise_catalog_uuid = request.GET.get('catalog')
        enterprise_catalog = None
        if enterprise_catalog_uuid:
            try:
                enterprise_catalog_uuid = UUID(enterprise_catalog_uuid)
                enterprise_catalog = enterprise_customer.enterprise_customer_catalogs.get(
                    uuid=enterprise_catalog_uuid
                )
            except (ValueError, EnterpriseCustomerCatalog.DoesNotExist):
                error_code = 'ENTCEV002'
                LOGGER.warning(
                    '[Enterprise Enrollment] EnterpriseCustomerCatalog does not exist. '
                    'ErrorCode: {error_code}, '
                    'EnterpriseCatalog: {enterprise_catalog_uuid}, '
                    'EnterpriseCustomer: {enterprise_uuid}, '
                    'CourseRun: {course_run_id}, '
                    'Username: {username}.'.format(
                        error_code=error_code,
                        enterprise_catalog_uuid=enterprise_catalog_uuid,
                        enterprise_uuid=enterprise_uuid,
                        course_run_id=course_run_id,
                        username=request.user.username,
                    )
                )
                messages.add_generic_error_message_with_code(request, error_code)

        course = None
        course_run = None
        course_modes = []
        if enterprise_catalog:
            course, course_run = enterprise_catalog.get_course_and_course_run(course_run_id)
        else:
            try:
                course, course_run = get_course_catalog_api_service_client(
                    enterprise_customer.site
                ).get_course_and_course_run(course_run_id)
            except ImproperlyConfigured:
                error_code = 'ENTCEV003'
                LOGGER.warning(
                    '[Enterprise Enrollment] CourseCatalogApiServiceClient is improperly configured. '
                    'ErrorCode: {error_code}, '
                    'Site: {enterprise_customer_site} '
                    'EnterpriseCustomer: {enterprise_uuid}, '
                    'CourseRun: {course_run_id}, '
                    'Username: {username}.'.format(
                        enterprise_customer_site=enterprise_customer.site.domain,
                        error_code=error_code,
                        enterprise_uuid=enterprise_uuid,
                        course_run_id=course_run_id,
                        username=request.user.username,
                    )
                )
                messages.add_generic_error_message_with_code(request, error_code)
                return enterprise_customer, course, course_run, course_modes

        if not course or not course_run:
            error_code = 'ENTCEV004'
            course_id = course['key'] if course else "Not Found"
            course_title = course['title'] if course else "Not Found"
            course_run_title = course_run['title'] if course_run else "Not Found"
            enterprise_catalog_title = enterprise_catalog.title if enterprise_catalog else "Not Found"
            # The specified course either does not exist in the specified
            # EnterpriseCustomerCatalog, or does not exist at all in the
            # discovery service.
            LOGGER.warning(
                '[Enterprise Enrollment] Failed to fetch details for course or course run. '
                'ErrorCode: {error_code}, '
                'Course: {course_id}, '
                'CourseRun: {course_run_id}, '
                'CourseRunTitle: {course_run_title}, '
                'CourseTitle: {course_title}, '
                'Username: {username}, '
                'EnterpriseCatalog: {enterprise_catalog_uuid}, '
                'EnterpriseCatalogTitle: {enterprise_catalog_title}, '
                'EnterpriseCustomer: {enterprise_uuid}, '
                'EnterpriseName: {enterprise_name}'.format(
                    error_code=error_code,
                    course_title=course_title,
                    course_id=course_id,
                    course_run_title=course_run_title,
                    course_run_id=course_run_id,
                    username=request.user.username,
                    enterprise_name=enterprise_customer.name,
                    enterprise_uuid=enterprise_customer.uuid,
                    enterprise_catalog_title=enterprise_catalog_title,
                    enterprise_catalog_uuid=enterprise_catalog_uuid,
                )
            )
            messages.add_generic_error_message_with_code(request, error_code)
            return enterprise_customer, course, course_run, course_modes

        if enterprise_catalog_uuid and not enterprise_catalog:
            # A catalog query parameter was given, but the specified
            # EnterpriseCustomerCatalog does not exist, so just return and
            # display the generic error message.
            return enterprise_customer, course, course_run, course_modes

        modes = self.get_available_course_modes(request, course_run_id, enterprise_catalog)
        audit_modes = getattr(
            settings,
            'ENTERPRISE_COURSE_ENROLLMENT_AUDIT_MODES',
            [constants.CourseModes.AUDIT, constants.CourseModes.HONOR]
        )

        for mode in modes:
            if mode['min_price']:
                price_text = get_price_text(mode['min_price'], request)
            else:
                price_text = _('FREE')
            if mode['slug'] in audit_modes:
                description = _('Not eligible for a certificate.')
            else:
                description = _('Earn a verified certificate!')
            course_modes.append({
                'mode': mode['slug'],
                'min_price': mode['min_price'],
                'sku': mode['sku'],
                'title': mode['name'],
                'original_price': price_text,
                'final_price': price_text,
                'description': description,
                'premium': mode['slug'] not in audit_modes
            })

        return enterprise_customer, course, course_run, course_modes

    def get_enterprise_course_enrollment_page(
            self,
            request,
            enterprise_customer,
            course,
            course_run,
            course_modes,
            enterprise_course_enrollment,
            data_sharing_consent
    ):
        """
        Render enterprise-specific course track selection page.
        """
        context_data = get_global_context(request, enterprise_customer)
        enterprise_catalog_uuid = request.GET.get(
            'catalog'
        ) if request.method == 'GET' else None
        html_template_for_rendering = ENTERPRISE_GENERAL_ERROR_PAGE
        if course and course_run:
            course_enrollable = True
            course_start_date = ''
            course_duration = ''
            course_in_future = False
            organization_name = ''
            organization_logo = ''
            expected_learning_items = course['expected_learning_items']
            # Parse organization name and logo.
            if course['owners']:
                # The owners key contains the organizations associated with the course.
                # We pick the first one in the list here to meet UX requirements.
                organization = course['owners'][0]
                organization_name = organization['name']
                organization_logo = organization['logo_image_url']

            course_title = course_run['title']
            course_short_description = course_run['short_description'] or ''
            course_full_description = clean_html_for_template_rendering(course_run['full_description'] or '')
            course_pacing = self.PACING_FORMAT.get(course_run['pacing_type'], '')
            if course_run['start']:
                course_start_date = parse(course_run['start']).strftime('%B %d, %Y')
                now = datetime.datetime.now(pytz.UTC)
                course_in_future = parse(course_run['start']) > now
            if course_run['start'] and course_run['end'] and course_run['weeks_to_complete']:
                course_end_date = parse(course_run['end']).strftime('%B %d, %Y')
                weeks_to_complete = course_run['weeks_to_complete']
                course_duration = _('{num_weeks}, starting on {start_date} and ending at {end_date}').format(
                    num_weeks=ngettext(
                        '{} week',
                        '{} weeks',
                        weeks_to_complete
                    ).format(weeks_to_complete),
                    start_date=course_start_date,
                    end_date=course_end_date,
                )
            course_level_type = course_run.get('level_type', '')
            staff = course_run['staff']
            # Format the course effort string using the min/max effort fields for the course run.
            course_effort = ungettext_min_max(
                '{} hour per week',
                '{} hours per week',
                '{}-{} hours per week',
                course_run['min_effort'] or None,
                course_run['max_effort'] or None,
            ) or ''

            # Parse course run image.
            course_run_image = course_run['image'] or {}
            course_image_uri = course_run_image.get('src', '')

            # Retrieve the enterprise-discounted price from ecommerce.
            course_modes = self.set_final_prices(course_modes, request)
            premium_modes = [mode for mode in course_modes if mode['premium']]

            # Filter audit course modes.
            course_modes = filter_audit_course_modes(enterprise_customer, course_modes)

            # Allows automatic assignment to a cohort upon enrollment.
            cohort = request.GET.get('cohort')
            # Add a message to the message display queue if the learner
            # has gone through the data sharing consent flow and declined
            # to give data sharing consent.
            if enterprise_course_enrollment and not data_sharing_consent.granted:
                messages.add_consent_declined_message(request, enterprise_customer, course_run.get('title', ''))

            if not is_course_run_enrollable(course_run):
                messages.add_unenrollable_item_message(request, 'course')
                course_enrollable = False
            context_data.update({
                'course_enrollable': course_enrollable,
                'course_title': course_title,
                'course_short_description': course_short_description,
                'course_pacing': course_pacing,
                'course_start_date': course_start_date,
                'course_duration': course_duration,
                'course_in_future': course_in_future,
                'course_image_uri': course_image_uri,
                'course_modes': course_modes,
                'course_effort': course_effort,
                'course_full_description': course_full_description,
                'cohort': cohort,
                'organization_logo': organization_logo,
                'organization_name': organization_name,
                'course_level_type': course_level_type,
                'premium_modes': premium_modes,
                'expected_learning_items': expected_learning_items,
                'catalog': enterprise_catalog_uuid,
                'staff': staff,
                'discount_text': _('Discount provided by {strong_start}{enterprise_customer_name}{strong_end}').format(
                    enterprise_customer_name=enterprise_customer.name,
                    strong_start='<strong>',
                    strong_end='</strong>',
                ),
                'hide_course_original_price': enterprise_customer.hide_course_original_price
            })
            html_template_for_rendering = 'enterprise/enterprise_course_enrollment_page.html'

            LOGGER.info(
                '[ENTERPRISE ENROLLMENT PAGE] Context Data. Data: [%s]',
                {
                    'enterprise_customer_name': enterprise_customer.name,
                    'user': request.user.username,
                    'course': course.get('key'),
                    'course_run': course_run.get('key'),
                    'course_enrollable': course_enrollable,
                    'course_start_date': course_start_date,
                    'course_modes': course_modes,
                    'premium_modes': premium_modes,
                    'catalog': enterprise_catalog_uuid,
                    'hide_course_original_price': enterprise_customer.hide_course_original_price
                }
            )

        context_data.update({
            'page_title': _('Confirm your course'),
            'confirmation_text': _('Confirm your course'),
            'starts_at_text': _('Starts'),
            'view_course_details_text': _('View Course Details'),
            'select_mode_text': _('Please select one:'),
            'price_text': _('Price'),
            'continue_link_text': _('Continue'),
            'level_text': _('Level'),
            'effort_text': _('Effort'),
            'duration_text': _('Duration'),
            'close_modal_button_text': _('Close'),
            'expected_learning_items_text': _("What you'll learn"),
            'course_full_description_text': _('About This Course'),
            'staff_text': _('Course Staff'),
        })
        return render(request, html_template_for_rendering, context=context_data)

    @method_decorator(enterprise_login_required)
    def post(self, request, enterprise_uuid, course_id):
        """
        Process a submitted track selection form for the enterprise.
        """
        enterprise_customer, course, course_run, course_modes = self.get_base_details(
            request, enterprise_uuid, course_id
        )
        enrollment_source = EnterpriseEnrollmentSource.get_source(
            EnterpriseEnrollmentSource.ENROLLMENT_URL
        )

        # Create a link between the user and the enterprise customer if it does not already exist.
        enterprise_customer_user, __ = EnterpriseCustomerUser.objects.update_or_create(
            enterprise_customer=enterprise_customer,
            user_id=request.user.id,
            defaults={'active': True},
        )
        enterprise_customer_user.update_session(request)

        data_sharing_consent = DataSharingConsent.objects.proxied_get(
            username=enterprise_customer_user.username,
            course_id=course_id,
            enterprise_customer=enterprise_customer
        )
        try:
            enterprise_course_enrollment = EnterpriseCourseEnrollment.objects.get(
                enterprise_customer_user__enterprise_customer=enterprise_customer,
                enterprise_customer_user__user_id=request.user.id,
                course_id=course_id
            )

        except EnterpriseCourseEnrollment.DoesNotExist:
            enterprise_course_enrollment = None

        enterprise_catalog_uuid = request.POST.get('catalog')
        selected_course_mode_name = request.POST.get('course_mode')
        cohort_name = request.POST.get('cohort')

        selected_course_mode = None
        for course_mode in course_modes:
            if course_mode['mode'] == selected_course_mode_name:
                selected_course_mode = course_mode
                break

        if not selected_course_mode:
            return self.get_enterprise_course_enrollment_page(
                request,
                enterprise_customer,
                course,
                course_run,
                course_modes,
                enterprise_course_enrollment,
                data_sharing_consent
            )

        user_consent_needed = get_data_sharing_consent(
            enterprise_customer_user.username,
            enterprise_customer.uuid,
            course_id=course_id
        ).consent_required()
        if not selected_course_mode.get('premium') and not user_consent_needed:
            # For the audit course modes (audit, honor), where DSC is not
            # required, enroll the learner directly through enrollment API
            # client and redirect the learner to LMS courseware page.
            succeeded = True
            client = EnrollmentApiClient()
            try:
                client.enroll_user_in_course(
                    request.user.username,
                    course_id,
                    selected_course_mode_name,
                    cohort=cohort_name,
                    enterprise_uuid=str(enterprise_customer.uuid)
                )
            except HttpClientError as exc:
                succeeded = False
                default_message = 'No error message provided'
                try:
                    error_message = json.loads(exc.content.decode()).get('message', default_message)
                except ValueError:
                    error_message = default_message
                LOGGER.exception(
                    'Error while enrolling user %(user)s: %(message)s',
                    {'user': self.user_id, 'message': error_message},
                )
            if succeeded:
                try:
                    # Create the Enterprise backend database records for this course enrollment.
                    __, created = EnterpriseCourseEnrollment.objects.get_or_create(
                        enterprise_customer_user=enterprise_customer_user,
                        course_id=course_id,
                        defaults={
                            'source': enrollment_source
                        }
                    )
                    if created:
                        track_enrollment(
                            'course-landing-page-enrollment', request.user.id,
                            course_id, request.get_full_path(),
                        )
                except IntegrityError:
                    LOGGER.exception(
                        "[ENTERPRISE ENROLLMENT PAGE] IntegrityError on attempt at EnterpriseCourseEnrollment "
                        "for enterprise customer user with id [%s] and course id [%s]",
                        enterprise_customer_user.user_id, course_id,
                    )

            return redirect(LMS_COURSEWARE_URL.format(course_id=course_id))

        if user_consent_needed:
            # For the audit course modes (audit, honor) or for the premium
            # course modes (Verified, Prof Ed) where DSC is required, redirect
            # the learner to course specific DSC with enterprise UUID from
            # there the learner will be directed to the ecommerce flow after
            # providing DSC.
            query_string_params = {
                'course_mode': selected_course_mode_name,
            }
            if enterprise_catalog_uuid:
                query_string_params.update({'catalog': enterprise_catalog_uuid})

            next_url = '{handle_consent_enrollment_url}?{query_string}'.format(
                handle_consent_enrollment_url=reverse(
                    'enterprise_handle_consent_enrollment', args=[enterprise_customer.uuid, course_id]
                ),
                query_string=urlencode(query_string_params)
            )

            failure_url = reverse('enterprise_course_run_enrollment_page', args=[enterprise_customer.uuid, course_id])
            if request.META['QUERY_STRING']:
                # Preserve all querystring parameters in the request to build
                # failure url, so that learner views the same enterprise course
                # enrollment page (after redirect) as for the first time.
                # Since this is a POST view so use `request.META` to get
                # querystring instead of `request.GET`.
                # https://docs.djangoproject.com/en/1.11/ref/request-response/#django.http.HttpRequest.META
                failure_url = '{course_enrollment_url}?{query_string}'.format(
                    course_enrollment_url=reverse(
                        'enterprise_course_run_enrollment_page', args=[enterprise_customer.uuid, course_id]
                    ),
                    query_string=request.META['QUERY_STRING']
                )

            return redirect(
                '{grant_data_sharing_url}?{params}'.format(
                    grant_data_sharing_url=reverse('grant_data_sharing_permissions'),
                    params=urlencode(
                        {
                            'next': next_url,
                            'failure_url': failure_url,
                            'enterprise_customer_uuid': enterprise_customer.uuid,
                            'course_id': course_id,
                        }
                    )
                )
            )

        # For the premium course modes (Verified, Prof Ed) where DSC is
        # not required, redirect the enterprise learner to the ecommerce
        # flow in LMS.
        # Note: LMS start flow automatically detects the paid mode
        premium_flow = LMS_START_PREMIUM_COURSE_FLOW_URL.format(course_id=course_id)
        if enterprise_catalog_uuid:
            premium_flow += '?catalog={catalog_uuid}'.format(
                catalog_uuid=enterprise_catalog_uuid
            )

        return redirect(premium_flow)

    @method_decorator(enterprise_login_required)
    @method_decorator(force_fresh_session)
    def get(self, request, enterprise_uuid, course_id):
        """
        Show course track selection page for the enterprise.

        Based on `enterprise_uuid` in URL, the view will decide which
        enterprise customer's course enrollment page is to use.

        Unauthenticated learners will be redirected to enterprise-linked SSO.

        A 404 will be raised if any of the following conditions are met:
            * No enterprise customer uuid kwarg `enterprise_uuid` in request.
            * No enterprise customer found against the enterprise customer
                uuid `enterprise_uuid` in the request kwargs.
            * No course is found in database against the provided `course_id`.

        """
        # Check to see if access to the course run is restricted for this user.
        embargo_url = EmbargoApiClient.redirect_if_blocked(
            request=request,
            course_run_ids=[course_id],
            user=request.user,
        )
        if embargo_url:
            return redirect(embargo_url)

        enterprise_customer, course, course_run, modes = self.get_base_details(
            request, enterprise_uuid, course_id
        )
        enterprise_customer_user = get_enterprise_customer_user(request.user.id, enterprise_uuid)
        data_sharing_consent = DataSharingConsent.objects.proxied_get(
            username=enterprise_customer_user.username,
            course_id=course_id,
            enterprise_customer=enterprise_customer
        )

        enrollment_client = EnrollmentApiClient()
        enrolled_course = enrollment_client.get_course_enrollment(request.user.username, course_id)
        try:
            enterprise_course_enrollment = EnterpriseCourseEnrollment.objects.get(
                enterprise_customer_user__enterprise_customer=enterprise_customer,
                enterprise_customer_user__user_id=request.user.id,
                course_id=course_id
            )
        except EnterpriseCourseEnrollment.DoesNotExist:
            enterprise_course_enrollment = None

        if enrolled_course and enterprise_course_enrollment:
            # The user is already enrolled in the course through the Enterprise Customer, so redirect to the course
            # info page.
            return redirect(LMS_COURSEWARE_URL.format(course_id=course_id))

        return self.get_enterprise_course_enrollment_page(
            request,
            enterprise_customer,
            course,
            course_run,
            modes,
            enterprise_course_enrollment,
            data_sharing_consent,
        )


class ProgramEnrollmentView(NonAtomicView):
    """
    Enterprise Program Enrollment landing page view.

    This view will display information pertaining to program enrollment,
    including the Enterprise offering the program, its (reduced) price,
    the courses within it, and whether one is already enrolled in them,
    and other several pieces of Enterprise context.
    """

    @staticmethod
    def extend_course(course, enterprise_customer, request):
        """
        Extend a course with more details needed for the program landing page.

        In particular, we add the following:

        * `course_image_uri`
        * `course_title`
        * `course_level_type`
        * `course_short_description`
        * `course_full_description`
        * `course_effort`
        * `expected_learning_items`
        * `staff`
        """
        course_run_id = course['course_runs'][0]['key']
        try:
            catalog_api_client = get_course_catalog_api_service_client(enterprise_customer.site)
        except ImproperlyConfigured:
            error_code = 'ENTPEV000'
            LOGGER.error(
                '[Enterprise Enrollment] CourseCatalogApiServiceClient is improperly configured. '
                'CourseRun: {course_run_id}, '
                'EnterpriseCustomer: {enterprise_customer}, '
                'ErrorCode: {error_code}, '
                'User: {userid}'.format(
                    error_code=error_code,
                    userid=request.user.id,
                    enterprise_customer=enterprise_customer.uuid,
                    course_run_id=course_run_id,
                )
            )
            messages.add_generic_error_message_with_code(request, error_code)
            return ({}, error_code)

        course_details, course_run_details = catalog_api_client.get_course_and_course_run(course_run_id)
        if not course_details or not course_run_details:
            error_code = 'ENTPEV001'
            LOGGER.error(
                '[Enterprise Enrollment] Course_details or course_run_details not found. '
                'CourseRun: {course_run_id}, '
                'EnterpriseCustomer: {enterprise_customer}, '
                'ErrorCode: {error_code}, '
                'User: {userid}'.format(
                    userid=request.user.id,
                    enterprise_customer=enterprise_customer.uuid,
                    course_run_id=course_run_id,
                    error_code=error_code,
                )
            )
            messages.add_generic_error_message_with_code(request, error_code)
            return ({}, error_code)

        weeks_to_complete = course_run_details['weeks_to_complete']
        course_run_image = course_run_details['image'] or {}
        course.update({
            'course_image_uri': course_run_image.get('src', ''),
            'course_title': course_run_details['title'],
            'course_level_type': course_run_details.get('level_type', ''),
            'course_short_description': course_run_details['short_description'] or '',
            'course_full_description': clean_html_for_template_rendering(course_run_details['full_description'] or ''),
            'expected_learning_items': course_details.get('expected_learning_items', []),
            'staff': course_run_details.get('staff', []),
            'course_effort': ungettext_min_max(
                '{} hour per week',
                '{} hours per week',
                '{}-{} hours per week',
                course_run_details['min_effort'] or None,
                course_run_details['max_effort'] or None,
            ) or '',
            'weeks_to_complete': ngettext(
                '{} week',
                '{} weeks',
                weeks_to_complete
            ).format(weeks_to_complete) if weeks_to_complete else '',
        })
        return course, None

    def get_program_details(self, request, program_uuid, enterprise_customer):
        """
        Retrieve fundamental details used by both POST and GET versions of this view.

        Specifically:

        * Take the program UUID and get specific details about the program.
        * Determine whether the learner is enrolled in the program.
        * Determine whether the learner is certificate eligible for the program.
        """
        try:
            course_catalog_api_client = get_course_catalog_api_service_client(enterprise_customer.site)
        except ImproperlyConfigured:
            error_code = 'ENTPEV002'
            LOGGER.error(
                '[Enterprise Enrollment] CourseCatalogApiServiceClient is improperly configured. '
                'EnterpriseCustomer: {enterprise_customer}, '
                'ErrorCode: {error_code}, '
                'Program: {program_uuid}, '
                'User: {userid}'.format(
                    error_code=error_code,
                    userid=request.user.id,
                    enterprise_customer=enterprise_customer.uuid,
                    program_uuid=program_uuid,
                )
            )
            messages.add_generic_error_message_with_code(request, error_code)
            return ({}, error_code)

        program_details = course_catalog_api_client.get_program_by_uuid(program_uuid)
        if program_details is None:
            error_code = 'ENTPEV003'
            LOGGER.error(
                '[Enterprise Enrollment] Program_details is None for program. '
                'EnterpriseCustomer: {enterprise_customer}, '
                'ErrorCode: {error_code}, '
                'Program: {program_uuid}, '
                'User: {userid}'.format(
                    userid=request.user.id,
                    enterprise_customer=enterprise_customer.uuid,
                    program_uuid=program_uuid,
                    error_code=error_code,
                )
            )
            messages.add_generic_error_message_with_code(request, error_code)
            return ({}, error_code)

        program_type = course_catalog_api_client.get_program_type_by_slug(slugify(program_details['type']))
        if program_type is None:
            error_code = 'ENTPEV004'
            LOGGER.error(
                '[Enterprise Enrollment] Program_type is None for program_details. '
                'EnterpriseCustomer: {enterprise_customer}, '
                'ErrorCode: {error_code}, '
                'Program: {program_uuid}, '
                'User: {userid}'.format(
                    userid=request.user.id,
                    enterprise_customer=enterprise_customer.uuid,
                    program_uuid=program_uuid,
                    error_code=error_code,
                )
            )
            messages.add_generic_error_message_with_code(request, error_code)
            return ({}, error_code)

        # Extend our program details with context we'll need for display or for deciding redirects.
        program_details = ProgramDataExtender(program_details, request.user).extend()

        # TODO: Upstream this additional context to the platform's `ProgramDataExtender` so we can avoid this here.
        program_details['enrolled_in_program'] = False
        enrollment_count = 0
        for extended_course in program_details['courses']:
            # We need to extend our course data further for modals and other displays.
            extended_data, error_code = ProgramEnrollmentView.extend_course(
                extended_course,
                enterprise_customer,
                request
            )

            if error_code:
                return ({}, error_code)

            extended_course.update(extended_data)
            # We're enrolled in the program if we have certificate-eligible enrollment in even 1 of its courses.
            extended_course_run = extended_course['course_runs'][0]
            if extended_course_run['is_enrolled'] and extended_course_run['upgrade_url'] is None:
                program_details['enrolled_in_program'] = True
                enrollment_count += 1

        # We're certificate eligible for the program if we have certificate-eligible enrollment in all of its courses.
        program_details['certificate_eligible_for_program'] = enrollment_count == len(program_details['courses'])
        program_details['type_details'] = program_type
        return program_details, None

    def get_enterprise_program_enrollment_page(self, request, enterprise_customer, program_details):
        """
        Render Enterprise-specific program enrollment page.
        """
        # Safely make the assumption that we can use the first authoring organization.
        organizations = program_details['authoring_organizations']
        organization = organizations[0] if organizations else {}
        platform_name = get_configuration_value('PLATFORM_NAME', settings.PLATFORM_NAME)
        program_title = program_details['title']
        program_type_details = program_details['type_details']
        program_type = program_type_details['name']

        # Make any modifications for singular/plural-dependent text.
        program_courses = program_details['courses']
        course_count = len(program_courses)
        course_count_text = ngettext(
            '{count} Course',
            '{count} Courses',
            course_count,
        ).format(count=course_count)
        effort_info_text = ungettext_min_max(
            '{} hour per week, per course',
            '{} hours per week, per course',
            _('{}-{} hours per week, per course'),
            program_details.get('min_hours_effort_per_week'),
            program_details.get('max_hours_effort_per_week'),
        )
        length_info_text = ungettext_min_max(
            '{} week per course',
            '{} weeks per course',
            _('{}-{} weeks per course'),
            program_details.get('weeks_to_complete_min'),
            program_details.get('weeks_to_complete_max'),
        )

        # Update some enrollment-related text requirements.
        if program_details['enrolled_in_program']:
            purchase_action = _('Purchase all unenrolled courses')
            item = _('enrollment')
        else:
            purchase_action = _('Pursue the program')
            item = _('program enrollment')

        # Add any DSC warning messages.
        program_data_sharing_consent = get_data_sharing_consent(
            request.user.username,
            enterprise_customer.uuid,
            program_uuid=program_details['uuid'],
        )
        if program_data_sharing_consent.exists and not program_data_sharing_consent.granted:
            messages.add_consent_declined_message(request, enterprise_customer, program_title)

        discount_data = program_details.get('discount_data', {})
        one_click_purchase_eligibility = program_details.get('is_learner_eligible_for_one_click_purchase', False)
        # The following messages shouldn't both appear at the same time, and we prefer the eligibility message.
        if not one_click_purchase_eligibility:
            messages.add_unenrollable_item_message(request, 'program')
        elif discount_data.get('total_incl_tax_excl_discounts') is None:
            messages.add_missing_price_information_message(request, program_title)

        context_data = get_global_context(request, enterprise_customer)
        context_data.update({
            'enrolled_in_course_and_paid_text': _('enrolled'),
            'enrolled_in_course_and_unpaid_text': _('already enrolled, must pay for certificate'),
            'expected_learning_items_text': _("What you'll learn"),
            'expected_learning_items_show_count': 2,
            'corporate_endorsements_text': _('Real Career Impact'),
            'corporate_endorsements_show_count': 1,
            'see_more_text': _('See More'),
            'see_less_text': _('See Less'),
            'confirm_button_text': _('Confirm Program'),
            'summary_header': _('Program Summary'),
            'price_text': _('Price'),
            'length_text': _('Length'),
            'effort_text': _('Effort'),
            'level_text': _('Level'),
            'course_full_description_text': _('About This Course'),
            'staff_text': _('Course Staff'),
            'close_modal_button_text': _('Close'),
            'program_not_eligible_for_one_click_purchase_text': _('Program not eligible for one-click purchase.'),
            'program_type_description_header': _('What is an {platform_name} {program_type}?').format(
                platform_name=platform_name,
                program_type=program_type,
            ),
            'platform_description_header': _('What is {platform_name}?').format(
                platform_name=platform_name
            ),
            'organization_name': organization.get('name'),
            'organization_logo': organization.get('logo_image_url'),
            'organization_text': _('Presented by {organization}').format(organization=organization.get('name')),
            'page_title': _('Confirm your {item}').format(item=item),
            'program_type_logo': program_type_details['logo_image'].get('medium', {}).get('url', ''),
            'program_type': program_type,
            'program_type_description': get_program_type_description(program_type),
            'program_title': program_title,
            'program_subtitle': program_details['subtitle'],
            'program_overview': program_details['overview'],
            'program_price': get_price_text(discount_data.get('total_incl_tax_excl_discounts', 0), request),
            'program_discounted_price': get_price_text(discount_data.get('total_incl_tax', 0), request),
            'is_discounted': discount_data.get('is_discounted', False),
            'courses': program_courses,
            'item_bullet_points': [
                _('Credit- and Certificate-eligible'),
                _('Self-paced; courses can be taken in any order'),
            ],
            'purchase_text': _('{purchase_action} for').format(purchase_action=purchase_action),
            'expected_learning_items': program_details['expected_learning_items'],
            'corporate_endorsements': program_details['corporate_endorsements'],
            'course_count_text': course_count_text,
            'length_info_text': length_info_text,
            'effort_info_text': effort_info_text,
            'is_learner_eligible_for_one_click_purchase': one_click_purchase_eligibility,
        })
        return render(request, 'enterprise/enterprise_program_enrollment_page.html', context=context_data)

    @method_decorator(enterprise_login_required)
    @method_decorator(force_fresh_session)
    def get(self, request, enterprise_uuid, program_uuid):
        """
        Show Program Landing page for the Enterprise's Program.

        Render the Enterprise's Program Enrollment page for a specific program.
        The Enterprise and Program are both selected by their respective UUIDs.

        Unauthenticated learners will be redirected to enterprise-linked SSO.

        A 404 will be raised if any of the following conditions are met:
            * No enterprise customer UUID query parameter ``enterprise_uuid`` found in request.
            * No enterprise customer found against the enterprise customer
                uuid ``enterprise_uuid`` in the request kwargs.
            * No Program can be found given ``program_uuid`` either at all or associated with
                the Enterprise..
        """
        verify_edx_resources()

        enterprise_customer = get_enterprise_customer_or_404(enterprise_uuid)
        context_data = get_global_context(request, enterprise_customer)
        program_details, error_code = self.get_program_details(request, program_uuid, enterprise_customer)
        if error_code:
            return render(
                request,
                ENTERPRISE_GENERAL_ERROR_PAGE,
                context=context_data,
                status=404,
            )
        if program_details['certificate_eligible_for_program']:
            # The user is already enrolled in the program, so redirect to the program's dashboard.
            return redirect(LMS_PROGRAMS_DASHBOARD_URL.format(uuid=program_uuid))

        # Check to see if access to any of the course runs in the program are restricted for this user.
        course_run_ids = []
        for course in program_details['courses']:
            for course_run in course['course_runs']:
                course_run_ids.append(course_run['key'])
        embargo_url = EmbargoApiClient.redirect_if_blocked(
            request=request,
            course_run_ids=course_run_ids,
            user=request.user,
        )
        if embargo_url:
            return redirect(embargo_url)

        return self.get_enterprise_program_enrollment_page(request, enterprise_customer, program_details)

    @method_decorator(enterprise_login_required)
    def post(self, request, enterprise_uuid, program_uuid):
        """
        Process a submitted track selection form for the enterprise.
        """
        verify_edx_resources()

        # Create a link between the user and the enterprise customer if it does not already exist.
        enterprise_customer = get_enterprise_customer_or_404(enterprise_uuid)
        with transaction.atomic():
            enterprise_customer_user, __ = EnterpriseCustomerUser.objects.update_or_create(
                enterprise_customer=enterprise_customer,
                user_id=request.user.id,
                defaults={'active': True},
            )
            enterprise_customer_user.update_session(request)

        context_data = get_global_context(request, enterprise_customer)
        program_details, error_code = self.get_program_details(request, program_uuid, enterprise_customer)
        if error_code:
            return render(
                request,
                ENTERPRISE_GENERAL_ERROR_PAGE,
                context=context_data,
                status=404,
            )
        if program_details['certificate_eligible_for_program']:
            # The user is already enrolled in the program, so redirect to the program's dashboard.
            return redirect(LMS_PROGRAMS_DASHBOARD_URL.format(uuid=program_uuid))

        basket_page = '{basket_url}?{params}'.format(
            basket_url=BASKET_URL,
            params=urlencode(
                [tuple(['sku', sku]) for sku in program_details['skus']] +
                [tuple(['bundle', program_uuid])]
            )
        )
        if get_data_sharing_consent(
                enterprise_customer_user.username,
                enterprise_customer.uuid,
                program_uuid=program_uuid,
        ).consent_required():
            return redirect(
                '{grant_data_sharing_url}?{params}'.format(
                    grant_data_sharing_url=reverse('grant_data_sharing_permissions'),
                    params=urlencode(
                        {
                            'next': basket_page,
                            'failure_url': reverse(
                                'enterprise_program_enrollment_page',
                                args=[enterprise_customer.uuid, program_uuid]
                            ),
                            'enterprise_customer_uuid': enterprise_customer.uuid,
                            'program_uuid': program_uuid,
                        }
                    )
                )
            )

        return redirect(basket_page)


class RouterView(NonAtomicView):
    """
    A router or gateway view for managing Enterprise workflows.
    """

    COURSE_ENROLLMENT_VIEW_URL = '/enterprise/{}/course/{}/enroll/'
    PROGRAM_ENROLLMENT_VIEW_URL = '/enterprise/{}/program/{}/enroll/'
    HANDLE_CONSENT_ENROLLMENT_VIEW_URL = '/enterprise/handle_consent_enrollment/{}/course/{}/'
    VIEWS = {
        COURSE_ENROLLMENT_VIEW_URL: CourseEnrollmentView,
        PROGRAM_ENROLLMENT_VIEW_URL: ProgramEnrollmentView,
        HANDLE_CONSENT_ENROLLMENT_VIEW_URL: HandleConsentEnrollment,
    }

    @staticmethod
    def get_path_variables(**kwargs):
        """
        Get the base variables for any view to route to.

        Currently gets:
        - `enterprise_uuid` - the UUID of the enterprise customer.
        - `course_run_id` - the ID of the course, if applicable.
        - `program_uuid` - the UUID of the program, if applicable.
        """
        enterprise_customer_uuid = kwargs.get('enterprise_uuid', '')
        course_run_id = kwargs.get('course_id', '')
        course_key = kwargs.get('course_key', '')
        program_uuid = kwargs.get('program_uuid', '')

        return enterprise_customer_uuid, course_run_id, course_key, program_uuid

    @staticmethod
    def get_course_run_id(user, enterprise_customer, course_key):
        """
        User is requesting a course, we need to translate that into the current course run.

        :param user:
        :param enterprise_customer:
        :param course_key:
        :return: course_run_id
        """
        try:
            course = get_course_catalog_api_service_client(enterprise_customer.site).get_course_details(course_key)
        except ImproperlyConfigured as error:
            raise Http404 from error

        users_all_enrolled_courses = EnrollmentApiClient().get_enrolled_courses(user.username)
        users_active_course_runs = get_active_course_runs(
            course,
            users_all_enrolled_courses
        ) if users_all_enrolled_courses else []
        course_run = get_current_course_run(course, users_active_course_runs)
        if course_run:
            course_run_id = course_run['key']
            return course_run_id
        raise Http404

    def eligible_for_direct_audit_enrollment(self, request, enterprise_customer, resource_id, course_key=None):
        """
        Return whether a request is eligible for direct audit enrollment for a particular enterprise customer.

        'resource_id' can be either course_run_id or program_uuid.
        We check for the following criteria:
        - The `audit` query parameter.
        - The user's being routed to the course enrollment landing page.
        - The customer's catalog contains the course in question.
        - The audit track is an available mode for the course.
        """
        course_identifier = course_key if course_key else resource_id

        # Return it in one big statement to utilize short-circuiting behavior. Avoid the API call if possible.
        return request.GET.get(constants.CourseModes.AUDIT) and \
            request.path == self.COURSE_ENROLLMENT_VIEW_URL.format(enterprise_customer.uuid, course_identifier) and \
            enterprise_customer.catalog_contains_course(resource_id) and \
            EnrollmentApiClient().has_course_mode(resource_id, constants.CourseModes.AUDIT)

    def redirect(self, request, *args, **kwargs):
        """
        Redirects to the appropriate view depending on where the user came from.
        """
        enterprise_customer_uuid, course_run_id, course_key, program_uuid = RouterView.get_path_variables(**kwargs)
        resource_id = course_key or course_run_id or program_uuid
        # Replace enterprise UUID and resource ID with '{}', to easily match with a path in RouterView.VIEWS. Example:
        # /enterprise/fake-uuid/course/course-v1:cool+course+2017/enroll/ -> /enterprise/{}/course/{}/enroll/
        path = re.sub('{}|{}'.format(enterprise_customer_uuid, re.escape(resource_id)), '{}', request.path)

        # Remove course_key from kwargs if it exists because delegate views are not expecting it.
        kwargs.pop('course_key', None)

        return self.VIEWS[path].as_view()(request, *args, **kwargs)

    @method_decorator(enterprise_login_required)
    @method_decorator(force_fresh_session)
    def get(self, request, *args, **kwargs):
        """
        Run some custom GET logic for Enterprise workflows before routing the user through existing views.

        In particular, before routing to existing views:

        - If the requested resource is a course, find the current course run for that course,
          and make that course run the requested resource instead.

        - Look to see whether a request is eligible for direct audit enrollment, and if so, directly enroll the user.
        """
        user_id = request.user.id
        enterprise_customer_uuid, course_run_id, course_key, program_uuid = RouterView.get_path_variables(**kwargs)
        enterprise_customer = get_enterprise_customer_or_404(enterprise_customer_uuid)
        if course_key:
            try:
                course_run_id = RouterView.get_course_run_id(request.user, enterprise_customer, course_key)
            except Http404:
                context_data = get_global_context(request, enterprise_customer)
                return render_page_with_error_code_message(
                    request, context_data, error_code=ROUTER_VIEW_NO_COURSE_ID_ERROR_CODE,
                    course_key=course_key, course_run_id=course_run_id, program_uuid=program_uuid,
                    enterprise_customer_uuid=enterprise_customer_uuid, user_id=request.user.id,
                )
            kwargs['course_id'] = course_run_id

            CornerstoneEnterpriseCustomerConfiguration = apps.get_model(
                'cornerstone',
                'CornerstoneEnterpriseCustomerConfiguration'
            )
            with transaction.atomic():
                # The presence of a sessionToken and subdomain param indicates a Cornerstone redirect
                # We need to store this sessionToken for api access
                csod_user_guid = request.GET.get('userGuid')
                csod_callback_url = request.GET.get('callbackUrl')
                csod_session_token = request.GET.get('sessionToken')
                csod_subdomain = request.GET.get("subdomain")
                if csod_session_token and csod_subdomain:
                    LOGGER.info(
                        f'integrated_channel=CSOD, '
                        f'integrated_channel_enterprise_customer_uuid={enterprise_customer.uuid}, '
                        f'integrated_channel_lms_user={user_id}, '
                        f'integrated_channel_course_key={course_key}, '
                        'enrollment redirect'
                    )
                    cornerstone_customer_configuration = \
                        CornerstoneEnterpriseCustomerConfiguration.get_by_customer_and_subdomain(
                            enterprise_customer=enterprise_customer,
                            customer_subdomain=csod_subdomain
                        )
                    if cornerstone_customer_configuration:
                        cornerstone_customer_configuration.session_token = csod_session_token
                        cornerstone_customer_configuration.session_token_modified = localized_utcnow()
                        cornerstone_customer_configuration.save()
                        create_cornerstone_learner_data(
                            user_id,
                            csod_user_guid,
                            csod_session_token,
                            csod_callback_url,
                            csod_subdomain,
                            cornerstone_customer_configuration,
                            course_key
                        )
                    else:
                        LOGGER.error(
                            f'integrated_channel=CSOD, '
                            f'integrated_channel_enterprise_customer_uuid={enterprise_customer.uuid}, '
                            f'integrated_channel_lms_user={request.user.id}, '
                            f'integrated_channel_course_key={course_key}, '
                            f'unable to find cornerstone config matching subdomain {request.GET.get("subdomain")}'
                        )

        # Ensure that the link is saved to the database prior to making some call in a downstream view
        # which may need to know that the user belongs to an enterprise customer.
        with transaction.atomic():
            enterprise_customer_user, __ = EnterpriseCustomerUser.objects.update_or_create(
                enterprise_customer=enterprise_customer,
                user_id=request.user.id,
                defaults={'active': True},
            )
            enterprise_customer_user.update_session(request)

        # Directly enroll in audit mode if the request in question has full direct audit enrollment eligibility.
        resource_id = course_run_id or program_uuid
        if self.eligible_for_direct_audit_enrollment(request, enterprise_customer, resource_id, course_key):
            try:
                enterprise_customer_user.enroll(
                    resource_id,
                    constants.CourseModes.AUDIT,
                    cohort=request.GET.get('cohort', None)
                )
                track_enrollment('direct-audit-enrollment', request.user.id, resource_id, request.get_full_path())
            except (CourseEnrollmentDowngradeError, CourseEnrollmentPermissionError):
                pass
            # The courseware view logic will check for DSC requirements, and route to the DSC page if necessary.
            return redirect(LMS_COURSEWARE_URL.format(course_id=resource_id))

        return self.redirect(request, *args, **kwargs)

    @method_decorator(enterprise_login_required)
    def post(self, request, *args, **kwargs):
        """
        Run some custom POST logic for Enterprise workflows before routing the user through existing views.
        """
        enterprise_customer_uuid, course_run_id, course_key, program_uuid = RouterView.get_path_variables(**kwargs)
        enterprise_customer = get_enterprise_customer_or_404(enterprise_customer_uuid)

        if course_key:
            context_data = get_global_context(request, enterprise_customer)
            try:
                kwargs['course_id'] = RouterView.get_course_run_id(request.user, enterprise_customer, course_key)
            except Http404:
                return render_page_with_error_code_message(
                    request, context_data, error_code=ROUTER_VIEW_NO_COURSE_ID_ERROR_CODE,
                    course_key=course_key, course_run_id=course_run_id, program_uuid=program_uuid,
                    enterprise_customer_uuid=enterprise_customer_uuid, userid=request.user.id,
                )

        return self.redirect(request, *args, **kwargs)
