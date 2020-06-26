"""
Module provides elements to be used in third-party auth pipeline.
"""

import re

from django.urls import reverse

from enterprise.models import EnterpriseCustomer, EnterpriseCustomerUser
from enterprise.utils import get_identity_provider

try:
    from social_core.pipeline.partial import partial
except ImportError:
    from enterprise.decorators import null_decorator as partial  # pylint:disable=ungrouped-imports

try:
    from social_django.models import UserSocialAuth
except ImportError:
    UserSocialAuth = None

try:
    from third_party_auth.provider import Registry
except ImportError:
    Registry = None

try:
    from openedx.core.djangoapps.user_api.accounts.utils import is_multiple_user_enterprises_feature_enabled
except ImportError:
    is_multiple_user_enterprises_feature_enabled = None


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
            enterprise_customer_identity_provider__provider_id=sso_provider_id
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
        if is_multiple_user_enterprises_feature_enabled() and not new_association:
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


def get_user_from_social_auth(tpa_provider, user_id):
    """
    Find the LMS user from the LMS model `UserSocialAuth`.

    Arguments:
        tpa_provider (third_party_auth.provider): third party auth provider object
        user_id (str): User id of user in third party LMS

    """
    provider_slug = tpa_provider.provider_id.strip('saml-')
    social_auth_uid = '{0}:{1}'.format(provider_slug, user_id)
    # we are filtering by both `provider` and `uid` to make use of provider,uid composite index
    # filtering only on `uid` makes query extremely slow since we don't have index on `uid`
    user_social_auth = UserSocialAuth.objects.select_related('user').filter(
        provider=tpa_provider.backend_name, uid=social_auth_uid
    ).first()

    return user_social_auth.user if user_social_auth else None


def get_user_social_auth(user, enterprise_customer):
    """
    Return social auth entry of user for given enterprise.

    Arguments:
        user (User): user object
        enterprise_customer (EnterpriseCustomer): User id of user in third party LMS

    """
    provider_id = enterprise_customer.identity_provider
    tpa_provider = get_identity_provider(provider_id)
    user_social_auth = UserSocialAuth.objects.filter(
        user=user,
        provider=tpa_provider.backend_name
    ).first()

    return user_social_auth


def handle_redirect_after_social_auth_login(backend, user):
    """
    Change the redirect url if user has more than 1 EnterpriseCustomer associations.

    Arguments:
        backend (User): social auth backend object
        user (User): user object

    """
    enterprise_customers_count = EnterpriseCustomerUser.objects.filter(user_id=user.id).count()
    next_url = backend.strategy.session_get('next')
    using_enrollment_url = re.match(r'/enterprise/.*/course/.*/enroll', str(next_url))
    if (enterprise_customers_count > 1) and not using_enrollment_url:
        select_enterprise_page_as_redirect_url(backend.strategy)


def select_enterprise_page_as_redirect_url(strategy):  # pylint: disable=invalid-name
    """
    Change the redirect url for the user to enterprise selection page.
    """
    current_redirect = strategy.session_get('next')
    select_enterprise_page = reverse('enterprise_select_active') + '?success_url=' + current_redirect
    strategy.session_set('next', select_enterprise_page)
