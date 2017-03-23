"""
User-facing views for the Enterprise app.
"""
from __future__ import absolute_import, unicode_literals

from edx_rest_api_client.exceptions import HttpClientError

from django.conf import settings
from django.core.urlresolvers import reverse
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import ugettext as _
from django.utils.translation import get_language_from_request
from django.views.generic import View

try:
    from edxmako.shortcuts import render_to_response
except ImportError:
    render_to_response = None

try:
    from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers
except ImportError:
    configuration_helpers = None

try:
    from third_party_auth.pipeline import (get_complete_url, get_real_social_auth_object, lift_quarantine,
                                           quarantine_session)
except ImportError:
    get_complete_url = None
    get_real_social_auth_object = None
    quarantine_session = None
    lift_quarantine = None


# isort:imports-firstparty
from enterprise.lms_api import CourseApiClient
from enterprise.models import (EnterpriseCourseEnrollment, EnterpriseCustomer, EnterpriseCustomerUser,
                               UserDataSharingConsentAudit)
from enterprise.tpa_pipeline import active_provider_enforces_data_sharing, get_enterprise_customer_for_request
from enterprise.utils import NotConnectedToEdX, consent_necessary_for_course


def verify_edx_resources():
    """
    Ensure that all necessary resources to render the view are present.
    """
    required_methods = (
        render_to_response,
        configuration_helpers,
        get_complete_url,
        get_real_social_auth_object,
        quarantine_session,
        lift_quarantine
    )
    if any(method is None for method in required_methods):
        raise NotConnectedToEdX(_('Methods in the Open edX platform necessary for this view are not available.'))


class GrantDataSharingPermissions(View):
    """
    Provide a form and form handler for data sharing consent.

    View handles the case in which we get to the "verify consent" step, but consent
    hasn't yet been provided - this view contains a GET view that provides a form for
    consent to be provided, and a POST view that consumes said form.
    """

    title_bar_prefix = _('Data sharing consent required')
    consent_message_header = _('Before enrollment is complete...')
    requested_permissions_header = _('{enterprise_customer_name} would like to know about:')
    agreement_text = _(
        'I agree to allow {platform_name} to share data about my enrollment, completion, and performance '
        'in all {platform_name} courses and programs where my enrollment is sponsored by {enterprise_customer_name}'
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
        _('What courses and/or programs I\'ve enrolled in'),
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
        ', and not to data from any {platform_name} courses or programs that I take on my own.'
    )
    confirmation_modal_header = _('Are you aware...')
    modal_affirm_decline_msg = _('I decline')
    modal_abort_decline_msg = _('View the data sharing policy')
    policy_link_template = _('View the {start_link}data sharing policy{end_link}.')
    policy_return_link_text = _('Return to Top')

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
            'title_bar_prefix': self.title_bar_prefix,
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
        }

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
        course_specific_context = {
            'consent_request_prompt': _(
                'To access this course and use your discount, you must first consent to share your '
                'learning achievements with {enterprise_customer_name}.'
            ).format(
                enterprise_customer_name=customer.name
            ),
            'confirmation_alert_prompt': _(
                'In order to start this course and use your discount, you must consent to share your '
                'course data with {enterprise_customer_name}.'
            ).format(
                enterprise_customer_name=customer.name
            ),
            'page_language': get_language_from_request(request),
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
            ]
        }
        context_data.update(course_specific_context)
        return render_to_response('grant_data_sharing_permissions.html', context_data, request=request)

    def get_account_consent(self, request):
        """
        Render a form to collect consent for account-wide data sharing.

        This method is called when no course ID is passed as a URL parameter; a form will be
        rendered with messaging around the concept of granting consent for the entire platform.
        """
        # Get the OpenEdX platform name
        platform_name = configuration_helpers.get_value("PLATFORM_NAME", settings.PLATFORM_NAME)

        # Get the EnterpriseCustomer for the request; raise an error if there isn't one.
        customer = get_enterprise_customer_for_request(request)
        if customer is None:
            raise Http404

        # Quarantine the user to this module.
        self.quarantine(request)

        failure_url = request.GET.get('failure_url')

        context_data = self.get_default_context(customer, platform_name)

        account_specific_context = {
            'consent_request_prompt': _(
                'To log in using this SSO identity provider and access special course offers, you must first '
                'consent to share your learning achievements with {enterprise_customer_name}.'
            ).format(
                enterprise_customer_name=customer.name
            ),
            'confirmation_alert_prompt': _(
                'In order to sign in and access special offers, you must consent to share your '
                'course data with {enterprise_customer_name}.'
            ).format(
                enterprise_customer_name=customer.name
            ),
            'page_language': get_language_from_request(request),
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
            ]
        }

        context_data.update(account_specific_context)

        return render_to_response('grant_data_sharing_permissions.html', context_data, request=request)

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

    def post_course_specific_consent(self, request, course_id, consent_provided):
        """
        Interpret the course-specific form above and save it to en EnterpriseCourseEnrollment object.
        """
        if not request.user.is_authenticated():
            raise Http404

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

        # Load the linked EnterpriseCustomer for this request. Return a 404 if no such EnterpriseCustomer exists
        customer = get_enterprise_customer_for_request(request)
        if customer is None:
            raise Http404

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

        ec_user, __ = EnterpriseCustomerUser.objects.get_or_create(
            user_id=user.id,
            enterprise_customer=customer,
        )

        UserDataSharingConsentAudit.objects.update_or_create(
            user=ec_user,
            defaults={
                'state': (
                    UserDataSharingConsentAudit.ENABLED if consent_provided
                    else UserDataSharingConsentAudit.DISABLED
                )
            }
        )

        # Resume auth pipeline
        backend_name = request.session.get('partial_pipeline', {}).get('backend')
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
