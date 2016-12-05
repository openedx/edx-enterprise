"""
User-facing views for the Enterprise app.
"""
from __future__ import absolute_import, unicode_literals

from django.conf import settings
from django.core.urlresolvers import reverse
from django.http import Http404
from django.shortcuts import redirect
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
from enterprise.models import EnterpriseCustomer, EnterpriseCustomerUser, UserDataSharingConsentAudit
from enterprise.tpa_pipeline import active_provider_enforces_data_sharing, get_enterprise_customer_for_request
from enterprise.utils import NotConnectedToEdX


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
        raise NotConnectedToEdX(_('Methods in the OpenEdX platform necessary for this view are not available.'))


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
                "Are you sure? If you do not agree to share your data, you will not get any "
                "discounts from {provider}."
            ).format(provider=provider)

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

    def get(self, request):
        """
        Render a form to collect user input about data sharing consent.
        """
        # Verify that all necessary resources are present
        verify_edx_resources()
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
            'sso_provider': customer.name,
            'data_sharing_consent': 'required' if required else 'optional',
            "messages": {
                "warning": self.get_warning(customer.name, platform_name, required),
                "note": self.get_note(customer.name, required),
            },
        }
        return render_to_response('grant_data_sharing_permissions.html', data, request=request)

    def post(self, request):
        """
        Process the above form.
        """
        # Verify that all necessary resources are present
        verify_edx_resources()
        self.lift_quarantine(request)
        customer = get_enterprise_customer_for_request(request)
        if customer is None:
            raise Http404
        consent_provided = request.POST.get('data_sharing_consent', False)
        # If the checkbox is unchecked, no value will be sent
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
