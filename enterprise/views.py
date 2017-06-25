"""
User-facing views for the Enterprise app.
"""
from __future__ import absolute_import, unicode_literals

from logging import getLogger

from dateutil.parser import parse
from edx_rest_api_client.exceptions import HttpClientError

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _
from django.utils.translation import get_language_from_request
from django.views.generic import View

try:
    from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers
except ImportError:
    configuration_helpers = None

try:
    from openedx.core.djangoapps.commerce.utils import ecommerce_api_client
except ImportError:
    ecommerce_api_client = None

try:
    from third_party_auth.pipeline import (
        get_complete_url,
        get_real_social_auth_object,
        lift_quarantine,
        quarantine_session,
        get as get_partial_pipeline
    )
except ImportError:
    get_complete_url = None
    get_real_social_auth_object = None
    quarantine_session = None
    lift_quarantine = None
    get_partial_pipeline = None

try:
    from util import organizations_helpers
except ImportError:
    organizations_helpers = None


# isort:imports-firstparty
from enterprise.constants import CONFIRMATION_ALERT_PROMPT, CONFIRMATION_ALERT_PROMPT_WARNING, CONSENT_REQUEST_PROMPT
from enterprise.course_catalog_api import CourseCatalogApiClient
from enterprise.decorators import enterprise_login_required
from enterprise.lms_api import CourseApiClient, EnrollmentApiClient
from enterprise.models import (
    EnterpriseCourseEnrollment,
    EnterpriseCustomer,
    EnterpriseCustomerUser,
    UserDataSharingConsentAudit,
)
from enterprise.tpa_pipeline import active_provider_enforces_data_sharing, get_enterprise_customer_for_request
from enterprise.utils import (
    NotConnectedToOpenEdX,
    consent_necessary_for_course,
    filter_audit_course_modes,
    get_enterprise_customer_or_404,
    get_enterprise_customer_user,
    is_consent_required_for_user,
)
from six.moves.urllib.parse import urlencode, urljoin  # pylint: disable=import-error


logger = getLogger(__name__)  # pylint: disable=invalid-name
LMS_DASHBOARD_URL = urljoin(settings.LMS_ROOT_URL, '/dashboard')
LMS_START_PREMIUM_COURSE_FLOW_URL = urljoin(settings.LMS_ROOT_URL, '/verify_student/start-flow/{course_id}/')
LMS_COURSEWARE_URL = urljoin(settings.LMS_ROOT_URL, '/courses/{course_id}/courseware')
LMS_COURSE_URL = urljoin(settings.LMS_ROOT_URL, '/courses/{course_id}/courseware')


def verify_edx_resources():
    """
    Ensure that all necessary resources to render the view are present.
    """
    required_methods = {
        'configuration_helpers': configuration_helpers,
        'get_enterprise_customer_for_request': get_enterprise_customer_for_request,
        'get_real_social_auth_object': get_real_social_auth_object,
        'quarantine_session': quarantine_session,
        'lift_quarantine': lift_quarantine,
        'get_partial_pipeline': get_partial_pipeline,
    }

    for method in required_methods:
        if required_methods[method] is None:
            raise NotConnectedToOpenEdX(
                _("The following method from the Open edX platform is necessary for this view but isn't available.")
                + "\nUnavailable: {method}".format(method=method)
            )


class GrantDataSharingPermissions(View):
    """
    Provide a form and form handler for data sharing consent.

    View handles the case in which we get to the "verify consent" step, but consent
    hasn't yet been provided - this view contains a GET view that provides a form for
    consent to be provided, and a POST view that consumes said form.
    """

    page_title = _('Data sharing consent required')
    consent_message_header = _('Before enrollment is complete...')
    requested_permissions_header = _('{enterprise_customer_name} would like to know about:')
    agreement_text = _(
        'I agree to allow {platform_name} to share data about my enrollment, completion, and performance '
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
        _('My email address for my {platform_name} account'),
        _('My {platform_name} ID'),
        _('My {platform_name} username'),
        _('What courses and/or programs I\'ve enrolled in or unenrolled from'),
        _(
            'Whether I completed specific parts of each course or program (for example, whether '
            'I watched a given video or completed a given homework assignment)'
        ),
        _('My overall percentage completion of each course or program on a periodic basis'),
        _('My performance in each course or program'),
        _('My final grade in each course or program'),
        _('Whether I received a certificate in each course or program'),
    ]
    sharable_items_footer = _(
        'My permission applies only to data from courses or programs that are sponsored by {enterprise_customer_name}'
        ', and not to data from any {platform_name} courses or programs that I take on my own. I understand that '
        'once I grant my permission to allow data to be shared with {enterprise_customer_name}, '
        'I may not withdraw my permission but I may elect to unenroll from any courses or programs that are '
        'sponsored by {enterprise_customer_name}.'
    )
    confirmation_modal_header = _('Are you aware...')
    modal_affirm_decline_msg = _('I decline')
    modal_abort_decline_msg = _('View the data sharing policy')
    policy_link_template = _('View the {start_link}data sharing policy{end_link}.').format(
        start_link='<a href="#consent-policy-dropdown-bar" class="policy-dropdown-link background-input" '
                   'id="policy-dropdown-link">',
        end_link='</a>',
    )
    policy_return_link_text = _('Return to Top')
    enterprise_welcome_text = _(
        "{strong_start}{enterprise_customer_name}{strong_end} has partnered with "
        "{strong_start}{platform_name}{strong_end} to offer you high-quality learning "
        "opportunities from the world's best universities."
    )

    @staticmethod
    def quarantine(request):
        """
        Set a session variable to quarantine the user to ``enterprise.views``.
        """
        quarantine_session(request, ('enterprise.views',))

    @staticmethod
    def lift_quarantine(request):
        """
        Remove the quarantine session variable.
        """
        lift_quarantine(request)

    def get_default_context(self, enterprise_customer, platform_name):
        """
        Get the set of variables that will populate the template by default.
        """
        return {
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
            'confirmation_modal_header': self.confirmation_modal_header,
            'confirmation_modal_affirm_decline_text': self.modal_affirm_decline_msg,
            'confirmation_modal_abort_decline_text': self.modal_abort_decline_msg,
            'policy_link_template': self.policy_link_template,
            'policy_return_link_text': self.policy_return_link_text,
            'LMS_SEGMENT_KEY': settings.LMS_SEGMENT_KEY,
        }

    @method_decorator(login_required)
    def get_course_specific_consent(self, request, course_id):
        """
        Render a form with course-specific information about data sharing consent.

        This particular variant of the method is called when a `course_id` parameter
        is passed to the view. In this case, the form is rendered with information
        about the specific course that's being set up.

        A 404 will be raised if any of the following conditions are met:
            * Enrollment is not to be deferred, but there is no EnterpriseCourseEnrollment
              associated with the current user.
            * Enrollment is not to be deferred and there's an EnterpriseCourseEnrollment
              associated with the current user, but the corresponding EnterpriseCustomer
              does not require course-level consent for this course.
            * Enrollment is to be deferred, but either no EnterpriseCustomer was
              supplied (via the enrollment_deferred GET parameter) or the supplied
              EnterpriseCustomer doesn't exist.
        """
        try:
            client = CourseApiClient()
            course_details = client.get_course_details(course_id)
        except HttpClientError:
            raise Http404
        next_url = request.GET.get('next')
        failure_url = request.GET.get('failure_url')

        enrollment_deferred = request.GET.get('enrollment_deferred')
        if enrollment_deferred is None:
            customer = get_object_or_404(
                EnterpriseCourseEnrollment,
                enterprise_customer_user__user_id=request.user.id,
                course_id=course_id
            ).enterprise_customer_user.enterprise_customer

            if not consent_necessary_for_course(request.user, course_id):
                raise Http404
        else:
            # For deferred enrollment, expect to receive the EnterpriseCustomer from the GET parameters,
            # which is used for display purposes.
            enterprise_uuid = request.GET.get('enterprise_id')
            if not enterprise_uuid:
                raise Http404
            customer = get_object_or_404(EnterpriseCustomer, uuid=enterprise_uuid)

        platform_name = configuration_helpers.get_value("PLATFORM_NAME", settings.PLATFORM_NAME)
        course_name = course_details['name']
        context_data = self.get_default_context(customer, platform_name)
        # Translators: bold_start and bold_end are HTML tags for specifying
        # enterprise name in bold text.
        course_specific_context = {
            'consent_request_prompt': _(
                'To access this course and use your discount, you must first consent to share your '
                'learning achievements with {bold_start}{enterprise_customer_name}{bold_end}.'
            ).format(
                enterprise_customer_name=customer.name,
                bold_start='<b>',
                bold_end='</b>',
            ),
            'confirmation_alert_prompt': _(
                'In order to start this course and use your discount, {bold_start}you must{bold_end} consent '
                'to share your course data with {enterprise_customer_name}.'
            ).format(
                enterprise_customer_name=customer.name,
                bold_start='<b>',
                bold_end='</b>',
            ),
            'confirmation_alert_prompt_warning': CONFIRMATION_ALERT_PROMPT_WARNING.format(  # pylint: disable=no-member
                enterprise_customer_name=customer.name,
            ),
            'LANGUAGE_CODE': get_language_from_request(request),
            'platform_name': platform_name,
            'course_id': course_id,
            'course_name': course_name,
            'redirect_url': next_url,
            'enterprise_customer_name': customer.name,
            'course_specific': True,
            'enrollment_deferred': enrollment_deferred is not None,
            'failure_url': failure_url,
            'requested_permissions': [
                _('your enrollment in this course'),
                _('your learning progress'),
                _('course completion'),
            ],
            'enterprise_customer': customer,
            'enterprise_welcome_text': self.enterprise_welcome_text.format(
                enterprise_customer_name=customer.name,
                platform_name=platform_name,
                strong_start='<strong>',
                strong_end='</strong>',
            )
        }
        context_data.update(course_specific_context)
        if customer.require_account_level_consent:
            context_data.update({
                'consent_request_prompt': _(
                    'To access this and other courses sponsored by {bold_start}{enterprise_customer_name}{bold_end}, '
                    'and to use the discounts available to you, you must first consent to share your '
                    'learning achievements with {bold_start}{enterprise_customer_name}{bold_end}.'
                ).format(
                    enterprise_customer_name=customer.name,
                    bold_start='<b>',
                    bold_end='</b>',
                ),
                'requested_permissions': [
                    _('your enrollment in all sponsored courses'),
                    _('your learning progress'),
                    _('course completion'),
                ],
            })

        return render(request, 'enterprise/grant_data_sharing_permissions.html', context=context_data)

    def get_account_consent(self, request):
        """
        Render a form to collect consent for account-wide data sharing.

        This method is called when no course ID is passed as a URL parameter; a form will be
        rendered with messaging around the concept of granting consent for the entire platform.
        """
        # Get the OpenEdX platform name
        platform_name = configuration_helpers.get_value("PLATFORM_NAME", settings.PLATFORM_NAME)

        # Get the EnterpriseCustomer for the request.
        customer = get_enterprise_customer_for_request(request)
        if customer is None:
            # If we can't get an EnterpriseCustomer from the pipeline, then we don't really
            # have enough state to do anything meaningful. Just send the user to the login
            # screen; if they want to sign in with an Enterprise-linked SSO, they can do
            # so, and the pipeline will get them back here if they need to be.
            return redirect('signin_user')

        # Quarantine the user to this module.
        self.quarantine(request)

        failure_url = request.GET.get('failure_url')

        context_data = self.get_default_context(customer, platform_name)

        account_specific_context = {
            'consent_request_prompt': CONSENT_REQUEST_PROMPT.format(  # pylint: disable=no-member
                enterprise_customer_name=customer.name
            ),
            'confirmation_alert_prompt': CONFIRMATION_ALERT_PROMPT.format(  # pylint: disable=no-member
                enterprise_customer_name=customer.name
            ),
            'confirmation_alert_prompt_warning': CONFIRMATION_ALERT_PROMPT_WARNING.format(  # pylint: disable=no-member
                enterprise_customer_name=customer.name,
            ),
            'LANGUAGE_CODE': get_language_from_request(request),
            'platform_name': platform_name,
            'enterprise_customer_name': customer.name,
            "course_id": None,
            "course_specific": False,
            'enrollment_deferred': False,
            'failure_url': failure_url,
            'requested_permissions': [
                _('your enrollment in all sponsored courses'),
                _('your learning progress'),
                _('course completion'),
            ],
            'enterprise_customer': customer,
            'enterprise_welcome_text': self.enterprise_welcome_text.format(
                enterprise_customer_name=customer.name,
                platform_name=platform_name,
                strong_start='<strong>',
                strong_end='</strong>',
            ),
        }

        context_data.update(account_specific_context)

        return render(request, 'enterprise/grant_data_sharing_permissions.html', context=context_data)

    def get(self, request):
        """
        Render a form to collect user input about data sharing consent.

        Based on a URL parameter, the form rendered will either be course-specific or appropriate
        for granting consent for all courses sponsored by the EnterpriseCustomer.
        """
        # Verify that all necessary resources are present
        verify_edx_resources()
        course = request.GET.get('course_id')
        if course:
            return self.get_course_specific_consent(request, course)
        return self.get_account_consent(request)

    @method_decorator(login_required)
    def post_course_specific_consent(self, request, course_id, consent_provided):
        """
        Interpret the course-specific form above and save it to en EnterpriseCourseEnrollment object.
        """
        try:
            client = CourseApiClient()
            client.get_course_details(course_id)
        except HttpClientError:
            raise Http404

        enrollment_deferred = request.POST.get('enrollment_deferred')
        if enrollment_deferred is None:
            EnterpriseCourseEnrollment.objects.update_or_create(
                enterprise_customer_user__user_id=request.user.id,
                course_id=course_id,
                defaults={
                    'consent_granted': consent_provided,
                }
            )
        if not consent_provided:
            failure_url = request.POST.get('failure_url') or reverse('dashboard')
            return redirect(failure_url)
        return redirect(request.POST.get('redirect_url', reverse('dashboard')))

    def post_account_consent(self, request, consent_provided):
        """
        Interpret the account-wide form above, and save it to a UserDataSharingConsentAudit object for later retrieval.
        """
        self.lift_quarantine(request)

        # Load the linked EnterpriseCustomer for this request.
        customer = get_enterprise_customer_for_request(request)
        if customer is None:
            # If we can't get an EnterpriseCustomer from the pipeline, then we don't really
            # have enough state to do anything meaningful. Just send the user to the login
            # screen; if they want to sign in with an Enterprise-linked SSO, they can do
            # so, and the pipeline will get them back here if they need to be.
            return redirect('signin_user')

        # Attempt to retrieve a user being manipulated by the third-party auth
        # pipeline. Return a 404 if no such user exists.
        social_auth = get_real_social_auth_object(request)
        user = getattr(social_auth, 'user', None)
        if user is None:
            raise Http404

        if not consent_provided and active_provider_enforces_data_sharing(request, EnterpriseCustomer.AT_LOGIN):
            # Flush the session to avoid the possibility of accidental login and to abort the pipeline.
            # pipeline is flushed only if data sharing is enforced, in other cases let the user to login.
            request.session.flush()
            failure_url = request.POST.get('failure_url') or reverse('dashboard')
            return redirect(failure_url)

        enterprise_customer_user, __ = EnterpriseCustomerUser.objects.get_or_create(
            user_id=user.id,
            enterprise_customer=customer,
        )

        platform_name = configuration_helpers.get_value('PLATFORM_NAME', settings.PLATFORM_NAME)
        messages.success(
            request,
            _('{span_start}Account created{span_end} Thank you for creating an account with {platform_name}.').format(
                platform_name=platform_name,
                span_start='<span>',
                span_end='</span>',
            )
        )
        if not user.is_active:
            messages.info(
                request,
                _(
                    '{span_start}Activate your account{span_end} Check your inbox for an activation email. '
                    'You will not be able to log back into your account until you have activated it.'
                ).format(span_start='<span>', span_end='</span>')
            )

        UserDataSharingConsentAudit.objects.update_or_create(
            user=enterprise_customer_user,
            defaults={
                'state': (
                    UserDataSharingConsentAudit.ENABLED if consent_provided
                    else UserDataSharingConsentAudit.DISABLED
                )
            }
        )

        # Resume auth pipeline
        backend_name = get_partial_pipeline(request).get('backend')
        return redirect(get_complete_url(backend_name))

    def post(self, request):
        """
        Process the above form.

        Use either a course-specific variant if a `course_id` form value is present,
        or otherwise, an account-wide variant.
        """
        # Verify that all necessary resources are present
        verify_edx_resources()

        # If the checkbox is unchecked, no value will be sent
        consent_provided = request.POST.get('data_sharing_consent', False)
        specific_course = request.POST.get('course_id')

        if specific_course:
            # We're handing consent only for a particular course
            return self.post_course_specific_consent(request, specific_course, consent_provided)
        return self.post_account_consent(request, consent_provided)


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
        # Verify that all necessary resources are present
        verify_edx_resources()
        enrollment_course_mode = request.GET.get('course_mode')

        # Redirect the learner to LMS dashboard in case no course mode is
        # provided as query parameter `course_mode`
        if not enrollment_course_mode:
            return redirect(LMS_DASHBOARD_URL)

        try:
            enrollment_client = EnrollmentApiClient()
            course_modes = enrollment_client.get_course_modes(course_id)
        except HttpClientError:
            logger.error('Failed to determine available course modes for course ID: %s', course_id)
            raise Http404

        # Verify that the request user belongs to the enterprise against the
        # provided `enterprise_uuid`.
        enterprise_customer = get_enterprise_customer_or_404(enterprise_uuid)
        enterprise_customer_user = get_enterprise_customer_user(request.user.id, enterprise_customer.uuid)
        if not enterprise_customer_user:
            raise Http404

        selected_course_mode = None
        for course_mode in course_modes:
            if course_mode['slug'] == enrollment_course_mode:
                selected_course_mode = course_mode
                break

        if not selected_course_mode:
            return redirect(LMS_DASHBOARD_URL)

        # Create the Enterprise backend database records for this course
        # enrollment
        EnterpriseCourseEnrollment.objects.update_or_create(
            enterprise_customer_user=enterprise_customer_user,
            course_id=course_id,
            defaults={
                'consent_granted': True,
            }
        )

        audit_modes = getattr(settings, 'ENTERPRISE_COURSE_ENROLLMENT_AUDIT_MODES', ['audit', 'honor'])
        if selected_course_mode['slug'] in audit_modes:
            # In case of Audit course modes enroll the learner directly through
            # enrollment API client and redirect the learner to dashboard.
            enrollment_api_client = EnrollmentApiClient()
            enrollment_api_client.enroll_user_in_course(
                request.user.username, course_id, selected_course_mode['slug']
            )

            return redirect(LMS_COURSEWARE_URL.format(course_id=course_id))

        # redirect the enterprise learner to the ecommerce flow in LMS
        # Note: LMS start flow automatically detects the paid mode
        return redirect(LMS_START_PREMIUM_COURSE_FLOW_URL.format(course_id=course_id))


class CourseEnrollmentView(View):
    """
    Enterprise landing page view.

    This view will display the course mode selection with related enterprise
    information.
    """

    pacing_options = {
        'instructor': _('Instructor-Paced'),
        'self': _('Self-Paced')
    }

    context_data = {
        'page_title': _('Choose Your Track'),
        'enterprise_welcome_text': _(
            "{strong_start}{enterprise_customer_name}{strong_end} has partnered with "
            "{strong_start}{platform_name}{strong_end} to offer you high-quality learning "
            "opportunities from the world's best universities."
        ),
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
            'Not eligible for a certificate; does not count toward a MicroMasters'
        ),
        'continue_link_text': _('Continue'),
        'level_text': _('Level'),
        'effort_text': _('Effort'),
        'effort_hours_text': _('{hours} hours per week, per course'),
        'close_modal_button_text': _('Close'),
    }

    def set_final_prices(self, modes, request):
        """
        Set the final discounted price on each premium mode.
        """
        result = []
        for mode in modes:
            if mode['premium']:
                mode['final_price'] = self.get_final_price(mode, request)
            result.append(mode)
        return result

    def get_final_price(self, mode, request):
        """
        Get course mode's SKU discounted price after applying any entitlement available for this user.
        """
        try:
            client = ecommerce_api_client(request.user)
            endpoint = client.baskets.calculate
            price_details = endpoint.get(sku=[mode['sku']])
            price = price_details['total_incl_tax']
            if price != mode['min_price']:
                return '${}'.format(price)
        except HttpClientError:
            logger.error(
                "Failed to get price details for course mode's SKU '{sku}' for username '{username}'".format(
                    sku=mode['sku'], username=request.user.username
                )
            )
        return mode['original_price']

    def get_base_details(self, enterprise_uuid, course_id):
        """
        Retrieve fundamental details used by both POST and GET versions of this view.

        Specifically, take an EnterpriseCustomer UUID and a course ID, and transform those
        into an actual EnterpriseCustomer, a set of details about the course, and a list
        of the available course modes for that course.
        """
        try:
            client = CourseApiClient()
            course_details = client.get_course_details(course_id)
        except HttpClientError:
            logger.error('Failed to get course details for course ID: %s', course_id)
            raise Http404

        if course_details is None:
            logger.error('Unable to find course details for course ID: %s', course_id)
            raise Http404

        enterprise_customer = get_enterprise_customer_or_404(enterprise_uuid)

        try:
            enrollment_client = EnrollmentApiClient()
            modes = enrollment_client.get_course_modes(course_id)
        except HttpClientError:
            logger.error('Failed to determine available course modes for course ID: %s', course_id)
            raise Http404

        course_modes = []

        audit_modes = getattr(
            settings,
            'ENTERPRISE_COURSE_ENROLLMENT_AUDIT_MODES',
            ['audit', 'honor']
        )

        for mode in modes:
            if mode['min_price']:
                price_text = '${}'.format(mode['min_price'])
            else:
                price_text = self.context_data['free_price_text']
            if mode['slug'] in audit_modes:
                description = self.context_data['audit_text']
            else:
                description = self.context_data['verified_text']
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

        return enterprise_customer, course_details, course_modes

    def get_enterprise_course_enrollment_page(self, request, enterprise_customer, course_details, course_modes):
        """
        Render enterprise specific course track selection page.
        """
        platform_name = configuration_helpers.get_value('PLATFORM_NAME', settings.PLATFORM_NAME)
        course_start_date = ''
        if course_details['start']:
            course_start_date = parse(course_details['start']).strftime('%B %d, %Y')

        try:
            effort_hours = int(course_details['effort'].split(':')[0])
        except (AttributeError, ValueError):
            course_effort = ''
        else:
            course_effort = self.context_data['effort_hours_text'].format(
                hours=effort_hours
            )
        course_run = CourseCatalogApiClient(request.user).get_course_run(course_details['course_id'])

        course_modes = self.set_final_prices(course_modes, request)
        premium_modes = [mode for mode in course_modes if mode['premium']]

        try:
            organization = organizations_helpers.get_organization(course_details['org'])
            organization_logo = organization['logo'].url
            organization_name = organization['name']
        except (TypeError, ValidationError, ValueError):
            organization_logo = None
            organization_name = None

        context_data = {
            'page_title': self.context_data['page_title'],
            'LANGUAGE_CODE': get_language_from_request(request),
            'platform_name': platform_name,
            'course_id': course_details['course_id'],
            'course_name': course_details['name'],
            'course_organization': course_details['org'],
            'course_short_description': course_details['short_description'] or '',
            'course_pacing': self.pacing_options.get(course_details['pacing'], ''),
            'course_start_date': course_start_date,
            'course_image_uri': course_details['media']['course_image']['uri'],
            'enterprise_customer': enterprise_customer,
            'enterprise_welcome_text': self.context_data['enterprise_welcome_text'].format(
                enterprise_customer_name=enterprise_customer.name,
                platform_name=platform_name,
                strong_start='<strong>',
                strong_end='</strong>',
            ),
            'confirmation_text': self.context_data['confirmation_text'],
            'starts_at_text': self.context_data['starts_at_text'],
            'view_course_details_text': self.context_data['view_course_details_text'],
            'select_mode_text': self.context_data['select_mode_text'],
            'price_text': self.context_data['price_text'],
            'continue_link_text': self.context_data['continue_link_text'],
            'course_modes': filter_audit_course_modes(enterprise_customer, course_modes),
            'course_effort': course_effort,
            'level_text': self.context_data['level_text'],
            'effort_text': self.context_data['effort_text'],
            'course_overview': course_details['overview'],
            'organization_logo': organization_logo,
            'organization_name': organization_name,
            'course_level_type': course_run.get('level_type', ''),
            'close_modal_button_text': self.context_data['close_modal_button_text'],
            'premium_modes': premium_modes,
        }
        return render(request, 'enterprise/enterprise_course_enrollment_page.html', context=context_data)

    @method_decorator(transaction.non_atomic_requests)
    def dispatch(self, *args, **kwargs):  # pylint: disable=arguments-differ
        """
        Disable atomicity for the view.

        Since we have settings.ATOMIC_REQUESTS enabled, Django wraps all view functions in an atomic transaction, so
        they can be rolled back if anything fails.

        However, the we need to be able to save data in the middle of get/post(), so that it's available for calls to
        external APIs.  To allow this, we need to disable atomicity at the top dispatch level.
        """
        return super(CourseEnrollmentView, self).dispatch(*args, **kwargs)

    @method_decorator(enterprise_login_required)
    def post(self, request, enterprise_uuid, course_id):
        """
        Process a submitted track selection form for the enterprise.
        """
        enterprise_customer, course, course_modes = self.get_base_details(enterprise_uuid, course_id)

        # Create a link between the user and the enterprise customer if it
        # does not already exist.
        enterprise_customer_user, __ = EnterpriseCustomerUser.objects.get_or_create(
            enterprise_customer=enterprise_customer,
            user_id=request.user.id
        )

        selected_course_mode_name = request.POST.get('course_mode')
        selected_course_mode = None
        for course_mode in course_modes:
            if course_mode['mode'] == selected_course_mode_name:
                selected_course_mode = course_mode
                break

        if not selected_course_mode:
            return self.get_enterprise_course_enrollment_page(request, enterprise_customer, course, course_modes)

        user_consent_needed = is_consent_required_for_user(enterprise_customer_user, course_id)
        if not selected_course_mode.get('premium') and not user_consent_needed:
            # For the audit course modes (audit, honor), where DSC is not
            # required, enroll the learner directly through enrollment API
            # client and redirect the learner to LMS courseware page.
            with transaction.atomic():
                # Create the Enterprise backend database records for this course
                # enrollment.
                EnterpriseCourseEnrollment.objects.get_or_create(
                    enterprise_customer_user=enterprise_customer_user,
                    course_id=course_id,
                )
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
            return redirect(
                '{grant_data_sharing_url}?{params}'.format(
                    grant_data_sharing_url=reverse('grant_data_sharing_permissions'),
                    params=urlencode(
                        {
                            'next': next_url,
                            'enterprise_id': enterprise_customer.uuid,
                            'course_id': course_id,
                            'enrollment_deferred': True,
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
        # Verify that all necessary resources are present
        verify_edx_resources()

        enterprise_customer, course, modes = self.get_base_details(enterprise_uuid, course_id)

        # Create a link between the user and the enterprise customer if it does not already exist.  Ensure that the link
        # is saved to the database prior to invoking get_final_price() on the displayed course modes, so that the
        # ecommerce service knows this user belongs to an enterprise customer.
        with transaction.atomic():
            EnterpriseCustomerUser.objects.get_or_create(
                enterprise_customer=enterprise_customer,
                user_id=request.user.id
            )

        enrollment_client = EnrollmentApiClient()
        enrolled_course = enrollment_client.get_course_enrollment(request.user.username, course_id)
        if (enrolled_course is not None and
                EnterpriseCourseEnrollment.objects.filter(
                    enterprise_customer_user__enterprise_customer=enterprise_customer,
                    enterprise_customer_user__user_id=request.user.id,
                    course_id=course_id
                ).exists()):
            # The user is already enrolled in the course through the Enterprise Customer, so redirect to the course
            # info page.
            return redirect(LMS_COURSE_URL.format(course_id=course_id))

        return self.get_enterprise_course_enrollment_page(request, enterprise_customer, course, modes)
