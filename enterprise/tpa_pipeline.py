"""
Module provides elements to be used in third-party auth pipeline.
"""

import re
from logging import getLogger

from django.urls import reverse

from enterprise.models import EnterpriseCustomer, EnterpriseCustomerUser
from enterprise.utils import get_identity_provider, get_social_auth_from_idp

try:
    from social_core.pipeline.partial import partial
except ImportError:
    from enterprise.decorators import null_decorator as partial  # pylint:disable=ungrouped-imports

try:
    from social_django.models import UserSocialAuth
except ImportError:
    UserSocialAuth = None

try:
    from common.djangoapps.third_party_auth.provider import Registry
except ImportError:
    Registry = None

LOGGER = getLogger(__name__)


def get_enterprise_customer_for_running_pipeline(request, pipeline):  # pylint: disable=invalid-name
    """
    Get the EnterpriseCustomer associated with a running pipeline.
    """
    sso_provider_id = request.GET.get('tpa_hint')
    if pipeline:
        sso_provider_id = Registry.get_from_pipeline(pipeline).provider_id
    return get_enterprise_customer_for_sso(sso_provider_id)


def get_enterprise_customer_for_sso(sso_provider_id):
    """
    Get the EnterpriseCustomer object tied to an identity provider.
    """
    try:
        return EnterpriseCustomer.objects.get(  # pylint: disable=no-member
            enterprise_customer_identity_providers__provider_id=sso_provider_id
        )
    except EnterpriseCustomer.DoesNotExist:
        return None


@partial
def handle_enterprise_logistration(backend, user, **kwargs):
    """
    Perform the linking of user in the process of logging to the Enterprise Customer.

    Args:
        backend: The class handling the SSO interaction (SAML, OAuth, etc)
        user: The user object in the process of being logged in with
        **kwargs: Any remaining pipeline variables

    """
    request = backend.strategy.request
    enterprise_customer = get_enterprise_customer_for_running_pipeline(
        request,
        {
            'backend': backend.name,
            'kwargs': kwargs
        }
    )
    if enterprise_customer is None:
        # This pipeline element is not being activated as a part of an Enterprise logistration

        # Social user account is new or already binded with edx account
        new_association = kwargs.get('new_association', True)
        if not new_association:
            handle_redirect_after_social_auth_login(backend, user)
        return

    # proceed with the creation of a link between the user and the enterprise customer, then exit.
    defaults = {'active': True}
    enterprise_customer_user, _ = EnterpriseCustomerUser.objects.update_or_create(
        enterprise_customer=enterprise_customer,
        user_id=user.id,
        defaults=defaults,
    )
    # if learner has activated enterprise we need to de-activate other enterprises learner is linked to
    EnterpriseCustomerUser.objects.filter(
        user_id=user.id
    ).exclude(enterprise_customer=enterprise_customer).update(active=False)
    enterprise_customer_user.update_session(request)


def get_user_from_social_auth(tpa_providers, user_id, enterprise_customer):
    """
    Find the LMS user from the LMS model `UserSocialAuth`.

    Arguments:
        tpa_providers (third_party_auth.provider): list of third party auth provider objects
        user_id (str): User id of user in third party LMS
        enterprise_customer (EnterpriseCustomer): Instance of the enterprise customer.

    """
    # Give the priority to default IDP of given enterprise when getting social auth entry of user. If found then
    # return it otherwise check social auth entry with other connected IDP's of enterprise.
    default_idp_user_social_auth = get_default_idp_user_social_auth(enterprise_customer, user_idp_id=user_id)
    if default_idp_user_social_auth:
        return default_idp_user_social_auth.user
    providers_backend_names = []
    social_auth_uids = []
    for idp in tpa_providers:
        tpa_provider = get_identity_provider(idp.provider_id)
        # We attach the auth type to the slug at some point in this flow,
        # so to match the original slug, we need to chop off that backend name.
        # We only use saml here, so we are removing the first 5 characters, ie 'saml-'
        provider_slug = tpa_provider.provider_id[5:]
        social_auth_uid = '{0}:{1}'.format(provider_slug, user_id)
        providers_backend_names.append(tpa_provider.backend_name)
        social_auth_uids.append(social_auth_uid)
    # we are filtering by both `provider` and `uid` to make use of provider,uid composite index
    # filtering only on `uid` makes query extremely slow since we don't have index on `uid`
    user_social_auth = UserSocialAuth.objects.select_related('user').filter(
        provider__in=providers_backend_names, uid__in=social_auth_uids
    ).first()

    return user_social_auth.user if user_social_auth else None


def get_user_social_auth(user, enterprise_customer):
    """
    Return social auth entry of user for given enterprise.

    Arguments:
        user (User): user object
        enterprise_customer (EnterpriseCustomer): Instance of the enterprise customer.

    """
    # Give the priority to default IDP of given enterprise when getting social auth entry of user. If found then
    # return it otherwise check social auth entry with other connected IDP's of enterprise.
    default_idp_user_social_auth = get_default_idp_user_social_auth(enterprise_customer, user=user)
    if default_idp_user_social_auth:
        return default_idp_user_social_auth
    provider_backend_names = []
    for idp in enterprise_customer.identity_providers:
        tpa_provider = get_identity_provider(idp.provider_id)
        provider_backend_names.append(tpa_provider.backend_name)
    user_social_auth = UserSocialAuth.objects.filter(provider__in=provider_backend_names, user=user).first()

    return user_social_auth


def get_default_idp_user_social_auth(enterprise_customer, user=None, user_idp_id=None):
    """
    Return social auth entry of user for given enterprise default IDP.

    Arguments:
        user (User): user object
        enterprise_customer (EnterpriseCustomer): Instance of the enterprise customer.
        user_idp_id (str): User id of user in third party LMS

    """
    return get_social_auth_from_idp(enterprise_customer.default_provider_idp, user=user, user_idp_id=user_idp_id)


def handle_redirect_after_social_auth_login(backend, user):
    """
    Change the redirect url if user has more than 1 EnterpriseCustomer associations.

    Arguments:
        backend (User): social auth backend object
        user (User): user object

    """
    enterprise_customers_count = EnterpriseCustomerUser.objects.filter(user_id=user.id).count()
    next_url = backend.strategy.session_get('next')
    if next_url is None:
        using_enrollment_url = re.match(r'/enterprise/.*/course/.*/enroll', str(next_url))
        if (enterprise_customers_count > 1) and not using_enrollment_url:
            select_enterprise_page_as_redirect_url(backend.strategy)
    else:
        LOGGER.info(
            'Could not locate redirect for user: {user_id} while handling multiple enterprises selection '
            'redirect.'.format(
                user_id=user.id
            )
        )


def select_enterprise_page_as_redirect_url(strategy):  # pylint: disable=invalid-name
    """
    Change the redirect url for the user to enterprise selection page.
    """
    current_redirect = strategy.session_get('next')
    select_enterprise_page = '{select_active_enterprise_view}?success_url={current_redirect}'.format(
        select_active_enterprise_view=reverse('enterprise_select_active'),
        current_redirect=current_redirect
    )
    strategy.session_set('next', select_enterprise_page)
