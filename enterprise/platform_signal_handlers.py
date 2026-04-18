"""
Signal handlers for platform-emitted Django signals consumed by edx-enterprise.
"""
from __future__ import annotations

import logging
from typing import Any

from social_core.backends.saml import SAMLAuth

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.http import HttpRequest

from enterprise.models import EnterpriseCustomerIdentityProvider, EnterpriseCustomerUser, PendingEnterpriseCustomerUser

log = logging.getLogger(__name__)


def _unlink_enterprise_user_from_idp(request: HttpRequest, user: AbstractUser, idp_backend_name: str) -> None:
    """
    Un-links learner from their enterprise identity provider.

    Args:
        request: The current HTTP request.
        user (User): User who initiated disconnect request.
        idp_backend_name (str): Name of identity provider's backend.
    """
    # Deferred imports — platform dependencies.
    from common.djangoapps.third_party_auth.provider import \
        Registry  # pylint: disable=import-outside-toplevel,import-error
    from openedx.features.enterprise_support.api import \
        enterprise_customer_for_request  # pylint: disable=import-outside-toplevel,import-error

    enterprise_customer = enterprise_customer_for_request(request)
    if user and enterprise_customer:
        enabled_providers = Registry.get_enabled_by_backend_name(idp_backend_name)
        provider_ids = [enabled_provider.provider_id for enabled_provider in enabled_providers]
        enterprise_customer_idps = EnterpriseCustomerIdentityProvider.objects.filter(
            enterprise_customer__uuid=enterprise_customer['uuid'],
            provider_id__in=provider_ids
        )

        if enterprise_customer_idps:
            try:
                # Unlink user email from each Enterprise Customer.
                for enterprise_customer_idp in enterprise_customer_idps:
                    EnterpriseCustomerUser.objects.unlink_user(
                        enterprise_customer=enterprise_customer_idp.enterprise_customer,
                        user_email=user.email,
                    )
            except (EnterpriseCustomerUser.DoesNotExist, PendingEnterpriseCustomerUser.DoesNotExist):
                pass


def handle_social_auth_disconnect(
    sender: type,  # pylint: disable=unused-argument
    *,  # Force everything that follows to be a keyword argument.
    request: HttpRequest | None,
    user: AbstractUser,
    saml_backend: SAMLAuth,
    **kwargs: Any,
) -> None:
    """
    Handle SAMLAccountDisconnected signal to unlink enterprise user from IdP.

    Arguments:
        sender: the class that sent the signal (unused).
        request: the HTTP request during which the disconnect occurred.
        user: the Django User disconnecting the social auth account.
        saml_backend: the SAML auth backend instance.
        **kwargs: forward-compatible catch-all.
    """
    if not settings.FEATURES.get('ENABLE_ENTERPRISE_INTEGRATION', False):
        return
    if request:
        _unlink_enterprise_user_from_idp(request, user, saml_backend.name)
