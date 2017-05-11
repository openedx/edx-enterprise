"""
Module provides elements to be used in third-party auth pipeline.
"""
from __future__ import absolute_import, unicode_literals

from django.conf import settings
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.shortcuts import redirect
from django.utils.translation import ugettext as _

from enterprise.models import EnterpriseCustomer, EnterpriseCustomerUser, UserDataSharingConsentAudit
from enterprise.utils import NotConnectedToEdX

try:
    from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers
except ImportError:
    configuration_helpers = None

try:
    from social.pipeline.partial import partial
except ImportError:
    from enterprise.utils import null_decorator as partial  # pylint:disable=ungrouped-imports

try:
    from third_party_auth.provider import Registry
except ImportError:
    Registry = None


def get_enterprise_customer_for_request(request):
    """
    Get the EnterpriseCustomer associated with a particular request.
    """
    pipeline = request.session.get('partial_pipeline')
    return get_ec_for_running_pipeline(pipeline)


def get_ec_for_running_pipeline(pipeline):
    """
    Get the EnterpriseCustomer associated with a running pipeline.
    """
    if Registry is None:
        raise NotConnectedToEdX(
            _("This package must be installed in an EdX environment to look up third-party auth providers.")
        )

    if pipeline is None:
        return None
    provider = Registry.get_from_pipeline(pipeline)
    return get_enterprise_customer_for_sso(provider)


def get_enterprise_customer_for_sso(provider):
    """
    Get the EnterpriseCustomer object tied to an identity provider.
    """
    if provider is None:
        return None
    try:
        return EnterpriseCustomer.objects.get(  # pylint: disable=no-member
            enterprise_customer_identity_provider__provider_id=provider.provider_id
        )
    except EnterpriseCustomer.DoesNotExist:
        return None


def active_provider_enforces_data_sharing(request, enforcement_location):
    """
    Check whether the active provider enforces data sharing consent.

    Determine two things - first, whether there's an active third-party
    identity provider currently running, and second, if that active provider
    enforces data sharing consent at the given point in order to proceed.

    Args:
        request: HttpRequest object containing request data.
        enforcement_location (str): the point where to see data sharing consent state.
        argument can either be "optional", 'at_login' or 'at_enrollment'
    """
    running_pipeline = request.session.get('partial_pipeline')
    if running_pipeline:
        customer = get_enterprise_customer_for_request(request)
        return customer and customer.enforces_data_sharing_consent(enforcement_location)
    return False


def active_provider_requests_data_sharing(request):
    """
    Determine if the active EnterpriseCustomer requests data sharing consent.
    """
    running_pipeline = request.session.get('partial_pipeline')
    if running_pipeline:
        customer = get_enterprise_customer_for_request(request)
        return customer and customer.requests_data_sharing_consent
    return False


def get_consent_status_for_pipeline(pipeline):
    """
    Get the consent object for the current pipeline.
    """
    customer = get_ec_for_running_pipeline(pipeline)
    user = pipeline.kwargs['user']
    try:
        return UserDataSharingConsentAudit.objects.get(
            user__user_id=user.id,
            user__enterprise_customer=customer,
        )
    except UserDataSharingConsentAudit.DoesNotExist:
        return None


@partial
def handle_enterprise_logistration(backend, user, **kwargs):
    """
    Perform tasks related to Enterprise-owned SSO signin requests.

    Checks to ensure that the user has provided data sharing consent
    if the active SSO provider requires it; if not, then the user will
    be redirected to a page from which they can provide consent.

    If consent is not required, then the user in the process of logging
    in is linked to the Enterprise Customer.

    Args:
        backend: The class handling the SSO interaction (SAML, OAuth, etc)
        user: The user object in the process of being logged in with
        **kwargs: Any remaining pipeline variables

    Returns:
        redirect: If consent is required, but has not been provided, the user
            is redirected to a page where they can provide consent.
    """
    def redirect_to_consent():
        """
        Redirect the user to a consent page.

        Method redirects the user to a page from which they can provide
        required data sharing consent before proceeding in the pipeline
        """
        return redirect(reverse('grant_data_sharing_permissions'))

    enterprise_customer = get_ec_for_running_pipeline({'backend': backend.name, 'kwargs': kwargs})
    if enterprise_customer is None:
        # This pipeline element is not being activated as a part of an Enterprise logistration
        return

    if not enterprise_customer.requests_data_sharing_consent:
        # This enterprise customer attached to this pipeline element does not request data sharing consent;
        # proceed with the creation of a link between the user and the enterprise customer, then exit.
        enterprise_customer_user, __ = EnterpriseCustomerUser.objects.get_or_create(
            enterprise_customer=enterprise_customer,
            user_id=user.id
        )

        platform_name = configuration_helpers.get_value('PLATFORM_NAME', settings.PLATFORM_NAME)
        messages.success(
            backend.strategy.request,
            _('{span_start}Account created{span_end} Thank you for creating an account with {platform_name}.').format(
                platform_name=platform_name,
                span_start='<span>',
                span_end='</span>',
            )
        )
        if not user.is_active:
            messages.info(
                backend.strategy.request,
                _(
                    '{span_start}Activate your account{span_end} Check your inbox for an activation email. '
                    'You will not be able to log back into your account until you have activated it.'
                ).format(span_start='<span>', span_end='</span>')
            )

        if (enterprise_customer.enforce_data_sharing_consent == EnterpriseCustomer.EXTERNALLY_MANAGED
                and enterprise_customer.enable_data_sharing_consent):

            UserDataSharingConsentAudit.objects.update_or_create(
                user=enterprise_customer_user,
                defaults={
                    'state': UserDataSharingConsentAudit.EXTERNALLY_MANAGED,
                }
            )

        return

    try:
        # Find an existing account-level consent record for the user
        consent = UserDataSharingConsentAudit.objects.get(
            user__user_id=user.id,
            user__enterprise_customer=enterprise_customer,
        )
    except UserDataSharingConsentAudit.DoesNotExist:
        return redirect_to_consent()

    if (not consent.enabled) and enterprise_customer.enforces_data_sharing_consent(EnterpriseCustomer.AT_LOGIN):
        # If consent has been declined, and the enterprise customer requires it, redirect to get it.
        return redirect_to_consent()
