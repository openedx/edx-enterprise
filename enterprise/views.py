# -*- coding: utf-8 -*-
"""
User-facing views for the Enterprise app.
"""
from __future__ import absolute_import, unicode_literals

import re
from logging import getLogger
from uuid import UUID

import waffle
from consent.helpers import get_data_sharing_consent
from consent.models import DataSharingConsent
from dateutil.parser import parse
from ipware.ip import get_ip

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ImproperlyConfigured
from django.core.urlresolvers import reverse
from django.db import transaction
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils.decorators import method_decorator
from django.utils.text import slugify
from django.utils.translation import ugettext as _
from django.utils.translation import get_language_from_request, ungettext
from django.views.generic import View

from enterprise import messages
from enterprise.api_client.discovery import CourseCatalogApiServiceClient
from enterprise.api_client.ecommerce import EcommerceApiClient
from enterprise.api_client.lms import CourseApiClient, EmbargoApiClient, EnrollmentApiClient
from enterprise.decorators import enterprise_login_required, force_fresh_session
from enterprise.models import EnterpriseCourseEnrollment, EnterpriseCustomerCatalog, EnterpriseCustomerUser
from enterprise.utils import (
    CourseEnrollmentDowngradeError,
    NotConnectedToOpenEdX,
    clean_html_for_template_rendering,
    filter_audit_course_modes,
    format_price,
    get_configuration_value,
    get_current_course_run,
    get_enterprise_customer_or_404,
    get_enterprise_customer_user,
    get_program_type_description,
    is_course_run_enrollable,
    track_enrollment,
    ungettext_min_max,
)
from six.moves.urllib.parse import urlencode, urljoin  # pylint: disable=import-error

try:
    from openedx.core.djangoapps.catalog.utils import get_localized_price_text
except ImportError:
    get_localized_price_text = None

try:
    from openedx.core.djangoapps.programs.utils import ProgramDataExtender
except ImportError:
    ProgramDataExtender = None

LOGGER = getLogger(__name__)
BASKET_URL = urljoin(settings.ECOMMERCE_PUBLIC_URL_ROOT, '/basket/add/')
LMS_DASHBOARD_URL = urljoin(settings.LMS_ROOT_URL, '/dashboard')
LMS_PROGRAMS_DASHBOARD_URL = urljoin(settings.LMS_ROOT_URL, '/dashboard/programs/{uuid}')
LMS_START_PREMIUM_COURSE_FLOW_URL = urljoin(settings.LMS_ROOT_URL, '/verify_student/start-flow/{course_id}/')
LMS_COURSEWARE_URL = urljoin(settings.LMS_ROOT_URL, '/courses/{course_id}/courseware')


def verify_edx_resources():
    """
    Ensure that all necessary resources to render the view are present.
    """
    required_methods = {
        'ProgramDataExtender': ProgramDataExtender,
    }

    for method in required_methods:
        if required_methods[method] is None:
            raise NotConnectedToOpenEdX(
                _("The following method from the Open edX platform is necessary for this view but isn't available.")
                + "\nUnavailable: {method}".format(method=method)
            )


def get_global_context(request):
    """
    Get the set of variables that are needed by default across views.
    """
    platform_name = get_configuration_value("PLATFORM_NAME", settings.PLATFORM_NAME)
    return {
        'LMS_SEGMENT_KEY': settings.LMS_SEGMENT_KEY,
        'LANGUAGE_CODE': get_language_from_request(request),
        'tagline': get_configuration_value(
            "ENTERPRISE_TAGLINE",
            getattr(settings, "ENTERPRISE_TAGLINE", '')  # Remove the `getattr` when setting is upstreamed.
        ),
        'platform_description': get_configuration_value(
            "PLATFORM_DESCRIPTION",
            getattr(settings, "PLATFORM_DESCRIPTION", '')  # Remove `getattr` when variable is upstreamed.
        ),
        'LMS_ROOT_URL': settings.LMS_ROOT_URL,
        'platform_name': platform_name,
        'header_logo_alt_text': _('{platform_name} home page').format(platform_name=platform_name),
    }


def get_price_text(price, request):
    """
    Return the localized converted price as string (ex. '$150 USD').

    If the local_currency switch is enabled and the users location has been determined this will convert the
    given price based on conversion rate from the Catalog service and return a localized string
    """
    if waffle.switch_is_active('local_currency') and get_localized_price_text:
        return get_localized_price_text(price, request)

    return format_price(price)


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
        return super(NonAtomicView, self).dispatch(request, *args, **kwargs)


class GrantDataSharingPermissions(View):
    """
    Provide a form and form handler for data sharing consent.

    View handles the case in which we get to the "verify consent" step, but consent
    hasn't yet been provided - this view contains a GET view that provides a form for
    consent to be provided, and a POST view that consumes said form.
    """

    page_title = _('Data sharing consent required')
    consent_message_header = _('Consent to share your data')
    requested_permissions_header = _('{enterprise_customer_name} would like to know about:')
    agreement_text = _(
        'I agree to allow {platform_name} to share data about my enrollment, completion and performance '
        'in all {platform_name} courses and programs where my enrollment is sponsored by {enterprise_customer_name}.'
    )
    continue_text = _('Yes, continue')
    abort_text = _('No, take me back.')
    policy_dropdown_header = _('Data Sharing Policy')
    sharable_items_header = _(
        'Enrollment, completion, and performance data that may be shared with {enterprise_customer_name} '
        '(or its designee) for these courses and programs are limited to the following:'
    )
    sharable_items = [
        _('My email address for my {platform_name} account, and the date when I created my {platform_name} account'),
        _('My {platform_name} ID, and if I log in via single sign-on, my {enterprise_customer_name} SSO user-ID'),
        _('My {platform_name} username'),
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
            'I watched a given video or completed a given homework assignment)'
        ),
        _(
            'My overall percentage completion of each course or program on a periodic basis, '
            'including the total time spent in each course or program and the date when I last '
            'logged in to each course or program'
        ),
        _('My performance in each course or program'),
        _('My final grade in each course or program, and the date when I completed each course or program'),
        _('Whether I received a certificate in each course or program'),
    ]
    sharable_items_footer = _(
        'My permission applies only to data from courses or programs that are sponsored by {enterprise_customer_name}, '
        'and not to data from any {platform_name} courses or programs that I take on my own. I understand that '
        'I may withdraw my permission only by fully unenrolling from any courses or programs that are sponsored by '
        '{enterprise_customer_name}.'
    )
    sharable_items_note_header = _('Please note')
    sharable_items_notes = [
        _('If you decline to consent, that fact may be shared with {enterprise_customer_name}.'),
    ]
    confirmation_modal_header = _('Are you aware...')
    modal_affirm_decline_msg = _('I decline')
    modal_abort_decline_msg = _('View the data sharing policy')
    policy_link_template = _('View the {start_link}data sharing policy{end_link}.').format(
        start_link='<a href="#consent-policy-dropdown-bar" class="policy-dropdown-link background-input" '
                   'id="policy-dropdown-link">',
        end_link='</a>',
    )
    policy_return_link_text = _('Return to Top')
    welcome_text = _('Welcome to {platform_name}.')
    enterprise_welcome_text = _(
        "{strong_start}{enterprise_customer_name}{strong_end} has partnered with "
        "{strong_start}{platform_name}{strong_end} to offer you high-quality learning "
        "opportunities from the world's best universities."
    )

    def course_or_program_exist(self, course_id, program_uuid):
        """
        Return whether the input course or program exist.
        """
        course_exists = course_id and CourseApiClient().get_course_details(course_id)
        program_exists = program_uuid and CourseCatalogApiServiceClient().program_exists(program_uuid)
        return course_exists or program_exists

    def get_default_context(self, enterprise_customer, request):
        """
        Get the set of variables that will populate the template by default.
        """
        context_data = get_global_context(request)
        platform_name = context_data['platform_name']
        context_data.update({
            'enterprise_customer': enterprise_customer,
            'welcome_text': self.welcome_text.format(platform_name=platform_name),
            'enterprise_welcome_text': self.enterprise_welcome_text.format(
                enterprise_customer_name=enterprise_customer.name,
                platform_name=platform_name,
                strong_start='<strong>',
                strong_end='</strong>',
            ),
            'page_title': self.page_title,
            'consent_message_header': self.consent_message_header,
            'requested_permissions_header': self.requested_permissions_header.format(
                enterprise_customer_name=enterprise_customer.name
            ),
            'agreement_text': self.agreement_text.format(
                enterprise_customer_name=enterprise_customer.name,
                platform_name=platform_name,
            ),
            'continue_text': self.continue_text,
            'abort_text': self.abort_text,
            'policy_dropdown_header': self.policy_dropdown_header,
            'sharable_items_header': self.sharable_items_header.format(
                enterprise_customer_name=enterprise_customer.name
            ),
            'sharable_items': [
                item.format(
                    enterprise_customer_name=enterprise_customer.name,
                    platform_name=platform_name
                ) for item in self.sharable_items
            ],
            'sharable_items_footer': self.sharable_items_footer.format(
                enterprise_customer_name=enterprise_customer.name,
                platform_name=platform_name,
            ),
            'sharable_items_note_header': self.sharable_items_note_header,
            'sharable_items_notes': [
                item.format(
                    enterprise_customer_name=enterprise_customer.name,
                    platform_name=platform_name
                ) for item in self.sharable_items_notes
            ],
            'confirmation_modal_header': self.confirmation_modal_header,
            'confirmation_modal_affirm_decline_text': self.modal_affirm_decline_msg,
            'confirmation_modal_abort_decline_text': self.modal_abort_decline_msg,
            'policy_link_template': self.policy_link_template,
            'policy_return_link_text': self.policy_return_link_text,
        })
        return context_data

    @method_decorator(login_required)
    def get(self, request):
        """
        Render a form to collect user input about data sharing consent.
        """
        enterprise_customer_uuid = request.GET.get('enterprise_customer_uuid')
        success_url = request.GET.get('next')
        failure_url = request.GET.get('failure_url')
        if not (enterprise_customer_uuid and success_url and failure_url):
            raise Http404

        course_id = request.GET.get('course_id', '')
        program_uuid = request.GET.get('program_uuid', '')
        if not self.course_or_program_exist(course_id, program_uuid):
            raise Http404

        consent_record = get_data_sharing_consent(
            request.user.username,
            enterprise_customer_uuid,
            program_uuid=program_uuid,
            course_id=course_id
        )
        if consent_record is None or not consent_record.consent_required():
            raise Http404

        item = 'course' if course_id else 'program'

        enterprise_customer = consent_record.enterprise_customer
        context_data = self.get_default_context(enterprise_customer, request)

        if course_id:
            try:
                catalog_api_client = CourseCatalogApiServiceClient(enterprise_customer.site)
            except ImproperlyConfigured:
                raise Http404

            course_run_details = catalog_api_client.get_course_run(course_id)
            course_start_date = ''
            if course_run_details['start']:
                course_start_date = parse(course_run_details['start']).strftime('%B %d, %Y')

            context_data.update({
                'course_id': course_id,
                'course_specific': True,
                'course_title': course_run_details['title'],
                'course_start_date': course_start_date,
            })
        else:
            context_data.update({
                'program_uuid': program_uuid,
                'program_specific': True,
            })

        # Translators: bold_start and bold_end are HTML tags for specifying enterprise name in bold text.
        context_data.update({
            'consent_request_prompt': _(
                'To access this {item}, you must first consent to share your learning achievements '
                'with {bold_start}{enterprise_customer_name}{bold_end}.'
            ).format(
                enterprise_customer_name=enterprise_customer.name,
                bold_start='<b>',
                bold_end='</b>',
                item=item,
            ),
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
            'confirmation_alert_prompt': _(
                'In order to start this {item} and use your discount, {bold_start}you must{bold_end} consent '
                'to share your {item} data with {enterprise_customer_name}.'
            ).format(
                enterprise_customer_name=enterprise_customer.name,
                bold_start='<b>',
                bold_end='</b>',
                item=item,
            ),
            'confirmation_alert_prompt_warning': '',
            'redirect_url': success_url,
            'failure_url': failure_url,
            'defer_creation': request.GET.get('defer_creation') is not None,
            'requested_permissions': [
                _('your enrollment in this {item}').format(item=item),
                _('your learning progress'),
                _('course completion'),
            ],
            'policy_link_template': '',
        })
        return render(request, 'enterprise/grant_data_sharing_permissions.html', context=context_data)

    @method_decorator(login_required)
    def post(self, request):
        """
        Process the above form.
        """
        enterprise_uuid = request.POST.get('enterprise_customer_uuid')
        success_url = request.POST.get('redirect_url')
        failure_url = request.POST.get('failure_url')
        if not (enterprise_uuid and success_url and failure_url):
            raise Http404

        course_id = request.POST.get('course_id', '')
        program_uuid = request.POST.get('program_uuid', '')
        if not self.course_or_program_exist(course_id, program_uuid):
            raise Http404

        consent_record = get_data_sharing_consent(
            request.user.username,
            enterprise_uuid,
            program_uuid=program_uuid,
            course_id=course_id
        )
        if consent_record is None:
            raise Http404

        defer_creation = request.POST.get('defer_creation')
        consent_provided = bool(request.POST.get('data_sharing_consent', False))
        if defer_creation is None and consent_record.consent_required():
            if course_id:
                enterprise_customer_user, __ = EnterpriseCustomerUser.objects.get_or_create(
                    enterprise_customer=consent_record.enterprise_customer,
                    user_id=request.user.id
                )
                __, created = EnterpriseCourseEnrollment.objects.get_or_create(
                    enterprise_customer_user=enterprise_customer_user,
                    course_id=course_id,
                )
                if created:
                    track_enrollment('data-consent-page-enrollment', request.user.id, course_id, request.path)

            consent_record.granted = consent_provided
            consent_record.save()

        return redirect(success_url if consent_provided else failure_url)


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

        # Redirect the learner to LMS dashboard in case no course mode is
        # provided as query parameter `course_mode`
        if not enrollment_course_mode:
            return redirect(LMS_DASHBOARD_URL)

        enrollment_api_client = EnrollmentApiClient()
        course_modes = enrollment_api_client.get_course_modes(course_id)
        if not course_modes:
            raise Http404

        # Verify that the request user belongs to the enterprise against the
        # provided `enterprise_uuid`.
        enterprise_customer = get_enterprise_customer_or_404(enterprise_uuid)
        enterprise_customer_user = get_enterprise_customer_user(request.user.id, enterprise_customer.uuid)

        selected_course_mode = None
        for course_mode in course_modes:
            if course_mode['slug'] == enrollment_course_mode:
                selected_course_mode = course_mode
                break

        if not selected_course_mode:
            return redirect(LMS_DASHBOARD_URL)

        # Create the Enterprise backend database records for this course
        # enrollment
        __, created = EnterpriseCourseEnrollment.objects.get_or_create(
            enterprise_customer_user=enterprise_customer_user,
            course_id=course_id,
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

        audit_modes = getattr(settings, 'ENTERPRISE_COURSE_ENROLLMENT_AUDIT_MODES', ['audit', 'honor'])
        if selected_course_mode['slug'] in audit_modes:
            # In case of Audit course modes enroll the learner directly through
            # enrollment API client and redirect the learner to dashboard.
            enrollment_api_client.enroll_user_in_course(
                request.user.username, course_id, selected_course_mode['slug']
            )

            return redirect(LMS_COURSEWARE_URL.format(course_id=course_id))

        # redirect the enterprise learner to the ecommerce flow in LMS
        # Note: LMS start flow automatically detects the paid mode
        return redirect(LMS_START_PREMIUM_COURSE_FLOW_URL.format(course_id=course_id))


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
    STATIC_TEXT_FORMAT = {
        'page_title': _('Confirm your course'),
        'confirmation_text': _('Confirm your course'),
        'starts_at_text': _('Starts'),
        'view_course_details_text': _('View Course Details'),
        'select_mode_text': _('Please select one:'),
        'price_text': _('Price'),
        'free_price_text': _('FREE'),
        'verified_text': _(
            'Earn a verified certificate!'
        ),
        'audit_text': _(
            'Not eligible for a certificate.'
        ),
        'continue_link_text': _('Continue'),
        'level_text': _('Level'),
        'effort_text': _('Effort'),
        'close_modal_button_text': _('Close'),
        'expected_learning_items_text': _("What you'll learn"),
        'course_full_description_text': _('About This Course'),
        'staff_text': _('Course Staff'),
    }
    WELCOME_TEXT_FORMAT = _('Welcome to {platform_name}.')
    ENT_WELCOME_TEXT_FORMAT = _(
        "{strong_start}{enterprise_customer_name}{strong_end} has partnered with "
        "{strong_start}{platform_name}{strong_end} to offer you high-quality learning "
        "opportunities from the world's best universities."
    )
    ENT_DISCOUNT_TEXT_FORMAT = _('Discount provided by {strong_start}{enterprise_customer_name}{strong_end}')

    def set_final_prices(self, modes, request):
        """
        Set the final discounted price on each premium mode.
        """
        result = []
        for mode in modes:
            if mode['premium']:
                mode['final_price'] = EcommerceApiClient(request.user).get_course_final_price(mode)
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
            LOGGER.warning('Unable to get course modes for course run id {course_run_id}.'.format(
                course_run_id=course_run_id
            ))
            messages.add_generic_info_message_for_error(request)

        if enterprise_catalog:
            # filter and order course modes according to the enterprise catalog
            modes = [mode for mode in modes if mode['slug'] in enterprise_catalog.enabled_course_modes]
            modes.sort(key=lambda course_mode: enterprise_catalog.enabled_course_modes.index(course_mode['slug']))
            if not modes:
                messages.add_generic_info_message_for_error(request)

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
                messages.add_generic_info_message_for_error(request)

        course = None
        course_run = None
        course_modes = []
        if enterprise_catalog:
            course, course_run = enterprise_catalog.get_course_and_course_run(course_run_id)
        else:
            try:
                course, course_run = CourseCatalogApiServiceClient(
                    enterprise_customer.site
                ).get_course_and_course_run(course_run_id)
            except ImproperlyConfigured:
                messages.add_generic_info_message_for_error(request)
                return enterprise_customer, course, course_run, course_modes

        if not course or not course_run:
            # The specified course either does not exist in the specified
            # EnterpriseCustomerCatalog, or does not exist at all in the
            # discovery service.
            LOGGER.warning(
                'Failed to fetch course [{course}] or course run [{course_run}] details for '
                'course run [{course_run_id}] enterprise [{enterprise_uuid}] '
                'catalog [{enterprise_catalog_uuid}]'.format(
                    course=course,
                    course_run=course_run,
                    course_run_id=course_run_id,
                    enterprise_uuid=enterprise_customer.uuid,
                    enterprise_catalog_uuid=enterprise_catalog_uuid,
                )
            )
            messages.add_generic_info_message_for_error(request)
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
            ['audit', 'honor']
        )

        for mode in modes:
            if mode['min_price']:
                price_text = get_price_text(mode['min_price'], request)
            else:
                price_text = self.STATIC_TEXT_FORMAT['free_price_text']
            if mode['slug'] in audit_modes:
                description = self.STATIC_TEXT_FORMAT['audit_text']
            else:
                description = self.STATIC_TEXT_FORMAT['verified_text']
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
        platform_name = get_configuration_value('PLATFORM_NAME', settings.PLATFORM_NAME)
        html_template_for_rendering = 'enterprise/enterprise_course_enrollment_error_page.html'
        context_data = {
            'enterprise_customer': enterprise_customer,
            'welcome_text': self.WELCOME_TEXT_FORMAT.format(platform_name=platform_name),
            'enterprise_welcome_text': self.ENT_WELCOME_TEXT_FORMAT.format(
                enterprise_customer_name=enterprise_customer.name,
                platform_name=platform_name,
                strong_start='<strong>',
                strong_end='</strong>',
            )
        }

        if course and course_run:
            course_enrollable = True
            course_start_date = ''
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
                'course_image_uri': course_image_uri,
                'course_modes': course_modes,
                'course_effort': course_effort,
                'course_full_description': course_full_description,
                'organization_logo': organization_logo,
                'organization_name': organization_name,
                'course_level_type': course_level_type,
                'premium_modes': premium_modes,
                'expected_learning_items': expected_learning_items,
                'staff': staff,
                'discount_text': self.ENT_DISCOUNT_TEXT_FORMAT.format(
                    enterprise_customer_name=enterprise_customer.name,
                    strong_start='<strong>',
                    strong_end='</strong>',
                )
            })
            html_template_for_rendering = 'enterprise/enterprise_course_enrollment_page.html'

        context_data.update(self.STATIC_TEXT_FORMAT)
        global_context_data = get_global_context(request)
        context_data.update(global_context_data)
        return render(request, html_template_for_rendering, context=context_data)

    @method_decorator(enterprise_login_required)
    def post(self, request, enterprise_uuid, course_id):
        """
        Process a submitted track selection form for the enterprise.
        """
        enterprise_customer, course, course_run, course_modes = self.get_base_details(
            request, enterprise_uuid, course_id
        )

        # Create a link between the user and the enterprise customer if it does not already exist.
        enterprise_customer_user, __ = EnterpriseCustomerUser.objects.get_or_create(
            enterprise_customer=enterprise_customer,
            user_id=request.user.id
        )

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

        selected_course_mode_name = request.POST.get('course_mode')
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
            if not enterprise_course_enrollment:
                # Create the Enterprise backend database records for this course enrollment.
                enterprise_course_enrollment = EnterpriseCourseEnrollment.objects.create(
                    enterprise_customer_user=enterprise_customer_user,
                    course_id=course_id,
                )
                track_enrollment('course-landing-page-enrollment', request.user.id, course_id, request.get_full_path())

            client = EnrollmentApiClient()
            client.enroll_user_in_course(request.user.username, course_id, selected_course_mode_name)

            return redirect(LMS_COURSEWARE_URL.format(course_id=course_id))

        if user_consent_needed:
            # For the audit course modes (audit, honor) or for the premium
            # course modes (Verified, Prof Ed) where DSC is required, redirect
            # the learner to course specific DSC with enterprise UUID from
            # there the learner will be directed to the ecommerce flow after
            # providing DSC.
            next_url = '{handle_consent_enrollment_url}?{query_string}'.format(
                handle_consent_enrollment_url=reverse(
                    'enterprise_handle_consent_enrollment', args=[enterprise_customer.uuid, course_id]
                ),
                query_string=urlencode({'course_mode': selected_course_mode_name})
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
        return redirect(LMS_START_PREMIUM_COURSE_FLOW_URL.format(course_id=course_id))

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
        embargo_url = EmbargoApiClient.redirect_if_blocked([course_id], request.user, get_ip(request), request.path)
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

    actions = {
        'purchase_unenrolled_courses': _('Purchase all unenrolled courses'),
        'purchase_program': _('Pursue the program'),
    }

    items = {
        'enrollment': _('enrollment'),
        'program_enrollment': _('program enrollment'),
    }

    context_data = {
        'program_type_description_header': _('What is an {platform_name} {program_type}?'),
        'platform_description_header': _('What is {platform_name}?'),
        'page_title': _('Confirm your {item}'),
        'organization_text': _('Presented by {organization}'),
        'item_bullet_points': [
            _('Credit- and Certificate-eligible'),
            _('Self-paced; courses can be taken in any order'),
        ],
        'purchase_text': _('{purchase_action} for'),
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
        'length_info_text': _('{}-{} weeks per course'),
        'effort_text': _('Effort'),
        'effort_info_text': _('{}-{} hours per week, per course'),
        'level_text': _('Level'),
        'course_full_description_text': _('About This Course'),
        'staff_text': _('Course Staff'),
        'close_modal_button_text': _('Close'),
        'program_not_eligible_for_one_click_purchase_text': _('Program not eligible for one-click purchase.'),
    }

    @staticmethod
    def extend_course(course, enterprise_customer):
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
        try:
            catalog_api_client = CourseCatalogApiServiceClient(enterprise_customer.site)
        except ImproperlyConfigured:
            raise Http404

        course_run_id = course['course_runs'][0]['key']
        course_details, course_run_details = catalog_api_client.get_course_and_course_run(course_run_id)
        if not course_details or not course_run_details:
            raise Http404

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
            'weeks_to_complete': ungettext(
                '{} week',
                '{} weeks',
                weeks_to_complete
            ).format(weeks_to_complete) if weeks_to_complete else '',
        })
        return course

    def get_program_details(self, request, program_uuid, enterprise_customer):
        """
        Retrieve fundamental details used by both POST and GET versions of this view.

        Specifically:

        * Take the program UUID and get specific details about the program.
        * Determine whether the learner is enrolled in the program.
        * Determine whether the learner is certificate eligible for the program.
        """
        try:
            course_catalog_api_client = CourseCatalogApiServiceClient(enterprise_customer.site)
        except ImproperlyConfigured:
            raise Http404

        program_details = course_catalog_api_client.get_program_by_uuid(program_uuid)
        if program_details is None:
            raise Http404

        program_type = course_catalog_api_client.get_program_type_by_slug(slugify(program_details['type']))
        if program_type is None:
            raise Http404

        # Extend our program details with context we'll need for display or for deciding redirects.
        program_details = ProgramDataExtender(program_details, request.user).extend()

        # TODO: Upstream this additional context to the platform's `ProgramDataExtender` so we can avoid this here.
        program_details['enrolled_in_program'] = False
        enrollment_count = 0
        for extended_course in program_details['courses']:
            # We need to extend our course data further for modals and other displays.
            extended_course.update(ProgramEnrollmentView.extend_course(extended_course, enterprise_customer))

            # We're enrolled in the program if we have certificate-eligible enrollment in even 1 of its courses.
            extended_course_run = extended_course['course_runs'][0]
            if extended_course_run['is_enrolled'] and extended_course_run['upgrade_url'] is None:
                program_details['enrolled_in_program'] = True
                enrollment_count += 1

        # We're certificate eligible for the program if we have certificate-eligible enrollment in all of its courses.
        program_details['certificate_eligible_for_program'] = (enrollment_count == len(program_details['courses']))
        program_details['type_details'] = program_type
        return program_details

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
        course_count_text = ungettext(
            '{count} Course',
            '{count} Courses',
            course_count,
        ).format(count=course_count)
        effort_info_text = ungettext_min_max(
            '{} hour per week, per course',
            '{} hours per week, per course',
            self.context_data['effort_info_text'],
            program_details.get('min_hours_effort_per_week'),
            program_details.get('max_hours_effort_per_week'),
        )
        length_info_text = ungettext_min_max(
            '{} week per course',
            '{} weeks per course',
            self.context_data['length_info_text'],
            program_details.get('weeks_to_complete_min'),
            program_details.get('weeks_to_complete_max'),
        )

        # Update some enrollment-related text requirements.
        if program_details['enrolled_in_program']:
            purchase_action = self.actions['purchase_unenrolled_courses']
            item = self.items['enrollment']
        else:
            purchase_action = self.actions['purchase_program']
            item = self.items['program_enrollment']

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

        # Update our context with the above calculated details and more.
        context_data = self.context_data.copy()
        context_data.update(get_global_context(request))
        context_data.update({
            'program_type_description_header': self.context_data['program_type_description_header'].format(
                platform_name=platform_name,
                program_type=program_type,
            ),
            'platform_description_header': self.context_data['platform_description_header'].format(
                platform_name=platform_name
            ),
            'enterprise_customer': enterprise_customer,
            'organization_name': organization.get('name'),
            'organization_logo': organization.get('logo_image_url'),
            'organization_text': self.context_data['organization_text'].format(organization=organization.get('name')),
            'page_title': self.context_data['page_title'].format(item=item),
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
            'item_bullet_points': self.context_data['item_bullet_points'],
            'purchase_text': self.context_data['purchase_text'].format(purchase_action=purchase_action),
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
        program_details = self.get_program_details(request, program_uuid, enterprise_customer)
        if program_details['certificate_eligible_for_program']:
            # The user is already enrolled in the program, so redirect to the program's dashboard.
            return redirect(LMS_PROGRAMS_DASHBOARD_URL.format(uuid=program_uuid))

        # Check to see if access to any of the course runs in the program are restricted for this user.
        course_run_ids = []
        for course in program_details['courses']:
            for course_run in course['course_runs']:
                course_run_ids.append(course_run['key'])
        embargo_url = EmbargoApiClient.redirect_if_blocked(course_run_ids, request.user, get_ip(request), request.path)
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
            enterprise_customer_user, __ = EnterpriseCustomerUser.objects.get_or_create(
                enterprise_customer=enterprise_customer,
                user_id=request.user.id
            )

        program_details = self.get_program_details(request, program_uuid, enterprise_customer)
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

    # pylint: disable=invalid-name
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

    def eligible_for_direct_audit_enrollment(self, request, enterprise_customer, course_run_id):
        """
        Return whether a request is eligible for direct audit enrollment for a particular enterprise customer.

        We check for the following criteria:
        - The `audit` query parameter.
        - The user's being routed to the course enrollment landing page.
        - The customer's catalog contains the course in question.
        - The audit track is an available mode for the course.
        """
        # Return it in one big statement to utilize short-circuiting behavior. Avoid the API call if possible.
        return request.GET.get('audit') and \
            request.path == self.COURSE_ENROLLMENT_VIEW_URL.format(enterprise_customer.uuid, course_run_id) and \
            enterprise_customer.catalog_contains_course(course_run_id) and \
            EnrollmentApiClient().has_course_mode(course_run_id, 'audit')

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
        enterprise_customer_uuid, course_run_id, course_key, program_uuid = RouterView.get_path_variables(**kwargs)
        enterprise_customer = get_enterprise_customer_or_404(enterprise_customer_uuid)

        if course_key:
            # User is requesting a course, we need to translate that into the current course run.
            try:
                course = CourseCatalogApiServiceClient(enterprise_customer.site).get_course_details(course_key)
            except ImproperlyConfigured:
                raise Http404

            course_run = get_current_course_run(course)
            if course_run:
                course_run_id = course_run['key']
                kwargs['course_id'] = course_run_id
            else:
                raise Http404

        # Ensure that the link is saved to the database prior to making some call in a downstream view
        # which may need to know that the user belongs to an enterprise customer.
        with transaction.atomic():
            enterprise_customer_user, __ = EnterpriseCustomerUser.objects.get_or_create(
                enterprise_customer=enterprise_customer,
                user_id=request.user.id
            )

        # Directly enroll in audit mode if the request in question has full direct audit enrollment eligibility.
        resource_id = course_run_id or program_uuid
        if self.eligible_for_direct_audit_enrollment(request, enterprise_customer, resource_id):
            try:
                enterprise_customer_user.enroll(resource_id, 'audit')
                track_enrollment('direct-audit-enrollment', request.user.id, resource_id, request.get_full_path())
            except CourseEnrollmentDowngradeError:
                pass
            # The courseware view logic will check for DSC requirements, and route to the DSC page if necessary.
            return redirect(LMS_COURSEWARE_URL.format(course_id=resource_id))

        return self.redirect(request, *args, **kwargs)

    @method_decorator(enterprise_login_required)
    def post(self, request, *args, **kwargs):
        """
        Run some custom POST logic for Enterprise workflows before routing the user through existing views.
        """
        return self.redirect(request, *args, **kwargs)
