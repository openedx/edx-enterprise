"""
Pipeline steps for the logistration (login/registration) filters.
"""
import logging
import re
import urllib.parse
from typing import Any

from crum import get_current_request
from openedx_filters.authentication.types import FormDescriptionProtocol, ProviderConfigProtocol, RunningPipeline
from openedx_filters.filters import PipelineStep

from django.conf import settings
from django.urls import reverse

try:
    from openedx.core.djangoapps.user_api import accounts
except ImportError:
    accounts = None

# ENT-11576: These functions will be migrated from the platform's enterprise_support module
# into edx-enterprise, eliminating these cross-boundary imports.
try:
    from openedx.features.enterprise_support.api import (
        activate_learner_enterprise,
        enterprise_customer_for_request,
        enterprise_enabled,
        get_enterprise_learner_data_from_api,
    )
    from openedx.features.enterprise_support.utils import (
        build_enterprise_branding_for_authn_mfe,
        get_enterprise_slug_login_url,
        handle_enterprise_cookies_for_logistration,
        update_logistration_context_for_enterprise,
    )
except ImportError:
    activate_learner_enterprise = None
    enterprise_customer_for_request = None
    enterprise_enabled = None
    get_enterprise_learner_data_from_api = None
    build_enterprise_branding_for_authn_mfe = None
    get_enterprise_slug_login_url = None
    handle_enterprise_cookies_for_logistration = None
    update_logistration_context_for_enterprise = None

log = logging.getLogger(__name__)

UUID4_REGEX = '[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}'


def _enterprise_enrollment_url_regex() -> str:
    """
    Return the regex matching enterprise direct-enrollment URLs.

    Built lazily because ``settings.COURSE_KEY_REGEX`` is only defined by the platform's
    settings, not by this package's standalone test settings.

    The customer UUID is captured as ``enterprise_uuid`` so callers can read it off the
    same match rather than applying a second regex to a different string.
    """
    return fr'/enterprise/(?P<enterprise_uuid>{UUID4_REGEX})/course/{settings.COURSE_KEY_REGEX}/enroll'


class LogistrationViewEnterpriseContextEnricher(PipelineStep):
    """
    Enrich the logistration page context with enterprise customer data.

    This step calls enterprise_customer_for_request to identify the enterprise customer
    associated with the current SSO session, then delegates to the enterprise_support
    utilities to update the context with enterprise-specific sidebar content and
    third-party-auth adjustments. It also injects the enterprise slug login URL and the
    enterprise-enabled flag consumed by the logistration page's JS.
    """

    def run_filter(self, context: dict[str, Any]) -> dict[str, Any]:  # pylint: disable=arguments-differ
        """
        Enrich context with enterprise customer data.
        """
        request = get_current_request()
        enterprise_customer = enterprise_customer_for_request(request)
        if enterprise_customer:
            log.info(
                "LogistrationViewEnterpriseContextEnricher running: enterprise_customer_uuid=%s",
                enterprise_customer.get('uuid'),
            )
        # Called even without an enterprise customer: it sets
        # context['enable_enterprise_sidebar'] = False and applies the third-party-auth
        # error message adjustments regardless of the customer.
        update_logistration_context_for_enterprise(request, context, enterprise_customer)

        if 'data' in context:
            context['data']['enterprise_slug_login_url'] = get_enterprise_slug_login_url()
            context['data']['is_enterprise_enable'] = enterprise_enabled()

        return {'context': context}


class AuthnMFEEnterpriseContextEnricher(PipelineStep):
    """
    Enrich the authentication MFE context with enterprise branding.

    This step is the authentication MFE counterpart to LogistrationViewEnterpriseContextEnricher. The MFE
    serves a flat context (as opposed to the legacy combined login/registration page's nested
    ``context['data']`` shape), so this step only adds the ``enterpriseBranding`` payload
    consumed by the authentication MFE, looked up from the enterprise customer associated with
    the current SSO session (``None`` when there is no enterprise customer).

    The payload goes into ``extra_context`` rather than ``context``: the platform's MFE context
    serializer declares no ``enterpriseBranding`` field, and drops undeclared ``context`` entries.
    Entries in ``extra_context`` are merged into the served response as-is, so this step owns the
    shape of its own payload.
    """

    def run_filter(  # pylint: disable=arguments-differ
        self, context: dict[str, Any], extra_context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Add enterprise branding to the authentication MFE context.
        """
        request = get_current_request()
        enterprise_customer = enterprise_customer_for_request(request)
        extra_context['enterpriseBranding'] = build_enterprise_branding_for_authn_mfe(enterprise_customer)
        return {'context': context, 'extra_context': extra_context}


class LogistrationViewEnterpriseCookieSetter(PipelineStep):
    """
    Set or delete enterprise cookies on the rendered logistration response.

    This step runs on every logistration page render (not only for enterprise customers),
    mirroring the original platform behavior: it sets the ``experiments_is_enterprise``
    cookie from ``context['enable_enterprise_sidebar']`` and deletes the enterprise
    customer cookie so that subsequent requests show the default login page.
    """

    def run_filter(self, response: Any, context: dict[str, Any]) -> dict[str, Any]:  # pylint: disable=arguments-differ
        """
        Apply enterprise cookie handling to the logistration response.
        """
        handle_enterprise_cookies_for_logistration(get_current_request(), response, context)
        return {'response': response, 'context': context}


class LoginFormEnterpriseOverrides(PipelineStep):
    """
    Override login form description fields for enterprise SSO users.

    The filter fires for every login form build, and passes the third-party auth state of the
    request. When the running pipeline's provider is known and the request is associated with
    an enterprise customer, the email field is pre-filled from the provider details and made
    read-only. Otherwise it is a no-op.
    """

    def run_filter(  # pylint: disable=arguments-differ
        self,
        form_desc: FormDescriptionProtocol,
        running_pipeline: RunningPipeline | None,
        current_provider: ProviderConfigProtocol | None,
    ) -> dict[str, Any]:
        """
        Apply enterprise SSO overrides to the login form description.
        """
        if running_pipeline and current_provider and enterprise_customer_for_request(get_current_request()):
            log.info(
                "LoginFormEnterpriseOverrides running: provider=%s",
                getattr(current_provider, 'provider_id', None),
            )
            email = running_pipeline['kwargs']['details'].get('email', '')

            # override the email field.
            form_desc.override_field_properties(
                "email",
                default=email,
                restrictions={"readonly": "readonly"} if email else {
                    "min_length": accounts.EMAIL_MIN_LENGTH,
                    "max_length": accounts.EMAIL_MAX_LENGTH,
                }
            )

        return {
            'form_desc': form_desc,
            'running_pipeline': running_pipeline,
            'current_provider': current_provider,
        }


class RegistrationFormEnterpriseOverrides(PipelineStep):
    """
    Override registration form description fields for enterprise SSO users.

    The filter fires for every registration form build, and passes the third-party auth state
    of the request. When the running pipeline's provider is configured to skip the registration
    form and we are in an enterprise context, we need to hide all fields except for terms of
    service and ensure that the user explicitly checks that field. Otherwise it is a no-op.

    The platform iterates its known registration fields and skips any without a provider
    override; this step iterates the provider overrides directly, which is equivalent
    because providers only return values for standard registration fields.
    """

    def run_filter(  # pylint: disable=arguments-differ
        self,
        form_desc: FormDescriptionProtocol,
        running_pipeline: RunningPipeline | None,
        current_provider: ProviderConfigProtocol | None,
    ) -> dict[str, Any]:
        """
        Hide provider-prefilled registration fields (except terms of service) for
        enterprise SSO registrations.
        """
        if (
                running_pipeline
                and current_provider
                and current_provider.skip_registration_form
                and enterprise_customer_for_request(get_current_request())
        ):
            log.info(
                "RegistrationFormEnterpriseOverrides running: provider=%s",
                getattr(current_provider, 'provider_id', None),
            )
            # Subscripted rather than ``.get()`` for the same reason as above: it preserves the
            # declared RunningPipelineKwargs shape that get_register_form_data expects.
            field_overrides = current_provider.get_register_form_data(running_pipeline['kwargs'])

            for field_name, field_default in field_overrides.items():
                # If SAML provider config has skip_registration_optional_checkboxes=True,
                # don't hide the marketing_emails_opt_in field (matching the platform's
                # guard around provider overrides for that field).
                #
                # NOTE: [2026-07-22] Reading this flag off current_provider is an intentional
                # divergence from the legacy platform logic, which ignored current_provider and
                # re-queried the database (SAMLProviderConfig.objects.current_set().get(slug=...)).
                # Using the config the running TPA pipeline already resolved is simpler, saves a
                # query, and reflects the config that actually drove the SSO handshake.
                #
                # That said, the old vs. new approach can still disagree in an unlikely corner
                # case: the new approach leverages a cache-backed value, while the old
                # queries the DB directly. We already take special care to invalidate the cache
                # on ``save()``, but not ``delete()``.  This really should NOT have an impact
                # in prod due to how slowly-changing these values are.
                if (
                        field_name == 'marketing_emails_opt_in'
                        and getattr(current_provider, 'skip_registration_optional_checkboxes', False)
                ):
                    continue

                if field_name not in ['terms_of_service', 'honor_code'] and field_default:
                    form_desc.override_field_properties(
                        field_name,
                        field_type="hidden",
                        default=field_default,
                        label="",
                        instructions="",
                    )

        return {
            'form_desc': form_desc,
            'running_pipeline': running_pipeline,
            'current_provider': current_provider,
        }


class PostLoginEnterpriseRedirect(PipelineStep):
    """
    Updates redirect url to enterprise selection page if user is associated
    with multiple enterprises otherwise return the next url.
    """

    def run_filter(self, redirect_url: str, user: Any) -> dict[str, Any]:  # pylint: disable=arguments-differ
        """
        Return enterprise selection page URL if user is associated with multiple enterprises.
        """
        learner_data = get_enterprise_learner_data_from_api(user)
        if learner_data and len(learner_data) > 1:
            log.info(
                "PostLoginEnterpriseRedirect running: user_id=%s linked to %s enterprises",
                user.id,
                len(learner_data),
            )
            # Check to see if the destination has an enterprise in it. In this case if user is associated
            # with that enterprise, activate that enterprise and bypass the selection page.
            url_match = re.match(_enterprise_enrollment_url_regex(), urllib.parse.unquote(redirect_url))
            if url_match:
                enterprise_in_url = url_match.group('enterprise_uuid')
                for enterprise in learner_data:
                    if enterprise_in_url == str(enterprise['enterprise_customer']['uuid']):
                        is_activated_successfully = activate_learner_enterprise(
                            get_current_request(), user, enterprise_in_url,
                        )
                        if is_activated_successfully:
                            # Already scoped to a single enterprise: leave the destination alone.
                            return {'redirect_url': redirect_url, 'user': user}
                        break

            # Carry the caller's destination through the selection page as success_url, so the
            # learner still lands there once they have chosen a customer.
            selection_url = (
                reverse('enterprise_select_active') + '/?success_url=' + urllib.parse.quote(redirect_url)
            )
            return {'redirect_url': selection_url, 'user': user}

        return {'redirect_url': redirect_url, 'user': user}
