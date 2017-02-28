"""
Module provides elements to be used in third-party auth pipeline.
"""
from __future__ import absolute_import, unicode_literals

from django.core.urlresolvers import reverse
from django.shortcuts import redirect
from django.utils.translation import ugettext as _

from enterprise.models import EnterpriseCustomer, EnterpriseCustomerUser, UserDataSharingConsentAudit
from enterprise.utils import NotConnectedToOpenEdx

try:
    from social_core.pipeline.partial import partial
except ImportError:
    from enterprise.utils import null_decorator as partial  # pylint:disable=ungrouped-imports

try:
    from third_party_auth.pipeline import get as get_pipeline_partial
except ImportError:
    get_pipeline_partial = None

try:
    from third_party_auth.provider import Registry
except ImportError:
    Registry = None


def verify_third_party_auth_dependencies():
    """
    Ensure that all necessary third_party_auth dependencies are present.
    """
    third_party_dependencies = (
        Registry,
        get_pipeline_partial,
    )

    if any(third_party_dependency is None for third_party_dependency in third_party_dependencies):
        raise NotConnectedToOpenEdx(
            _("This package must be installed in an Open edX environment to look up third-party auth dependencies.")
        )


def get_enterprise_customer_for_request(request):
    """
    Get the EnterpriseCustomer associated with a particular request.
    """
    verify_third_party_auth_dependencies()
    pipeline = get_pipeline_partial(request)
    return get_enterprise_customer_for_running_pipeline(pipeline)


def get_enterprise_customer_for_running_pipeline(pipeline):  # pylint: disable=invalid-name
    """
    Get the EnterpriseCustomer associated with a running pipeline.
    """
    verify_third_party_auth_dependencies()
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
    running_pipeline = request.session.get('partial_pipeline_token')
    if running_pipeline:
        customer = get_enterprise_customer_for_request(request)
        return customer and customer.enforces_data_sharing_consent(enforcement_location)
    return False


def active_provider_requests_data_sharing(request):
    """
    Determine if the active EnterpriseCustomer requests data sharing consent.
    """
    running_pipeline = request.session.get('partial_pipeline_token')
    if running_pipeline:
        customer = get_enterprise_customer_for_request(request)
        return customer and customer.requests_data_sharing_consent
    return False


def get_consent_status_for_pipeline(pipeline):
    """
    Get the consent object for the current pipeline.
    """
    customer = get_enterprise_customer_for_running_pipeline(pipeline)
    user = pipeline.kwargs['user']
    try:
        return UserDataSharingConsentAudit.objects.get(
            user__user_id=user.id,
            user__enterprise_customer=customer,
        )
    except UserDataSharingConsentAudit.DoesNotExist:
        return None


@partial
def verify_data_sharing_consent(backend, user, **kwargs):
    """
    Verify that the data sharing consent state matches what's required.

    Checks to ensure that the user has provided data sharing consent
    if the active SSO provider requires it; if not, then the user will
    be redirected to a page from which they can provide consent.
    """
    def redirect_to_consent():
        """
        Redirect the user to a consent page.

        Method redirects the user to a page from which they can provide
        required data sharing consent before proceeding in the pipeline
        """
        return redirect(reverse('grant_data_sharing_permissions'))

    customer = get_enterprise_customer_for_running_pipeline({'backend': backend.name, 'kwargs': kwargs})
    if customer is None:
        return

    if not customer.requests_data_sharing_consent:
        return

    try:
        consent = UserDataSharingConsentAudit.objects.get(
            user__user_id=user.id,
            user__enterprise_customer=customer,
        )
    except UserDataSharingConsentAudit.DoesNotExist:
        return redirect_to_consent()

    if (not consent.enabled) and customer.enforces_data_sharing_consent(EnterpriseCustomer.AT_LOGIN):
        return redirect_to_consent()


def set_data_sharing_consent_record(backend, user, data_sharing_consent=None, **kwargs):
    """
    Set the data sharing consent record as required.

    If the pipeline produced a command to explicitly set the data sharing consent
    record a particular way, set it that way.
    """
    if data_sharing_consent is None:
        return

    customer = get_enterprise_customer_for_running_pipeline({'backend': backend.name, 'kwargs': kwargs})
    if customer is None:
        return

    ec_user, _ = EnterpriseCustomerUser.objects.get_or_create(
        user_id=user.id,
        enterprise_customer=customer,
    )

    UserDataSharingConsentAudit.objects.update_or_create(
        user=ec_user,
        defaults={'state': 'enabled' if data_sharing_consent else 'disabled'}
    )
