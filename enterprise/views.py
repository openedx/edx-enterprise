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
    from third_party_auth.pipeline import (get_complete_url, get_real_social_auth_object, quarantine_session,
                                           lift_quarantine)
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

    @staticmethod
    def get_warning(provider, platform, required):
        """
        Get the appropriate warning for the form.
        """
        if required:
            return _(
                "Are you sure? If you do not agree to share your data, you will have to use "
                "another account to access {platform}."
            ).format(platform=platform)
        else:
            return _(
                "Are you sure? If you do not agree to share your data, you will not receive "
                "discounts from {provider}."
            ).format(provider=provider)

    @staticmethod
    def get_course_warning(provider, course_name):
        """
        Get a course-specific warning for the form.

        Arguments:
            provider: The name of the linked EnterpriseCustomer
            course_name: The name of the course in question
        """
        return _(
            "Are you sure? If you do not agree to share your data with {provider}, you cannot "
            "access {course_name}."
        ).format(provider=provider, course_name=course_name)

    @staticmethod
    def get_note(provider, required):
        """
        Get the appropriate note for the form.
        """
        if required:
            return _(
                "{provider} requires data sharing consent; if consent is not provided, you will"
                " be redirected to log in page."
            ).format(provider=provider)
        else:
            return _(
                "{provider} requests data sharing consent; if consent is not provided, you will"
                " not be able to get any discounts from {provider}."
            ).format(provider=provider)

    @staticmethod
    def get_course_note(provider, course_name):
        """
        Get a course-specific note for the form.

        Arguments:
            provider: The name of the linked EnterpriseCustomer
            course_name: The name of the course in question
        """
        return _(
            "Courses from {provider} require data sharing consent. If you do not agree to "
            "share your data, you will be redirected to your dashboard."
        ).format(provider=provider, course_name=course_name)

    def get_course_specific_consent(self, request, course_id):
        """
        Render a form with course-specific information about data sharing consent.

        This particular variant of the method is called when a `course_id` parameter
        is passed to the view. In this case, the form is rendered with information
        about the specific course that's being set up.
        """
        try:
            client = CourseApiClient()
            course_details = client.get_course_details(course_id)
        except HttpClientError:
            raise Http404
        next_url = request.GET.get('next')

        customer = get_object_or_404(
            EnterpriseCourseEnrollment,
            enterprise_customer_user__user_id=request.user.id,
            course_id=course_id
        ).enterprise_customer_user.enterprise_customer
        if not consent_necessary_for_course(request.user, course_id):
            raise Http404
        platform_name = configuration_helpers.get_value("PLATFORM_NAME", settings.PLATFORM_NAME)
        course_name = course_details['name']
        data = {
            'platform_name': platform_name,
            'data_sharing_consent': 'required',
            "messages": {
                "warning": self.get_course_warning(customer.name, course_name),
                "note": self.get_course_note(customer.name, course_name),
            },
            'course_id': course_id,
            'course_name': course_name,
            'redirect_url': next_url,
            'enterprise_customer_name': customer.name,
            'course_specific': True,
        }
        return render_to_response('grant_data_sharing_permissions.html', data, request=request)

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

        required = customer.enforces_data_sharing_consent(EnterpriseCustomer.AT_LOGIN)

        data = {
            'platform_name': platform_name,
            'enterprise_customer_name': customer.name,
            'data_sharing_consent': 'required' if required else 'optional',
            "messages": {
                "warning": self.get_warning(customer.name, platform_name, required),
                "note": self.get_note(customer.name, required),
            },
            "course_id": None,
            "course_specific": False,
        }
        return render_to_response('grant_data_sharing_permissions.html', data, request=request)

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

        EnterpriseCourseEnrollment.objects.update_or_create(
            enterprise_customer_user__user_id=request.user.id,
            course_id=course_id,
            defaults={
                'consent_granted': consent_provided,
            }
        )
        if not consent_provided:
            return redirect(reverse('dashboard'))
        return redirect(request.POST.get('redirect_url', reverse('dashboard')))

    def post_account_consent(self, request, consent_provided):
        """
        Interpret the account-wide form above, and save it to a UserDataSharingConsentAudit object for later retrieval.
        """
        self.lift_quarantine(request)
        customer = get_enterprise_customer_for_request(request)
        if customer is None:
            raise Http404
        user = get_real_social_auth_object(request).user
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
        if not consent_provided:
            # Flush the session to avoid the possibility of accidental login and to abort the pipeline.
            # pipeline is flushed only if data sharing is enforced, in other cases let the user to login.
            if active_provider_enforces_data_sharing(request, EnterpriseCustomer.AT_LOGIN):
                request.session.flush()
                return redirect(reverse('dashboard'))

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
