"""
Pipeline steps for the logistration (login/registration) filters.
"""
import logging
import re
import urllib.parse
from typing import Any

from crum import get_current_request
from openedx_filters.filters import PipelineStep
from openedx_filters.learning.filters import (
    FormDescriptionProtocol,
    LogistrationMFERedirectRequested,
    ProviderConfigProtocol,
)

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
        get_enterprise_slug_login_url,
        handle_enterprise_cookies_for_logistration,
        update_logistration_context_for_enterprise,
    )
except ImportError:
    activate_learner_enterprise = None
    enterprise_customer_for_request = None
    enterprise_enabled = None
    get_enterprise_learner_data_from_api = None
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
    """
    return fr'/enterprise/{UUID4_REGEX}/course/{settings.COURSE_KEY_REGEX}/enroll'


class LogistrationContextEnricher(PipelineStep):
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
                "LogistrationContextEnricher running: enterprise_customer_uuid=%s",
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


class LogistrationCookieSetter(PipelineStep):
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

    Only invoked while a third-party-auth pipeline is running (the platform triggers the
    filter exclusively from within its third-party-auth overrides). When the pipeline's
    provider is known and the request is associated with an enterprise customer, the email
    field is pre-filled from the provider details and made read-only.
    """

    def run_filter(  # pylint: disable=arguments-differ
        self,
        form_desc: FormDescriptionProtocol,
        running_pipeline: dict,
        current_provider: ProviderConfigProtocol | None,
    ) -> dict[str, Any]:
        """
        Apply enterprise SSO overrides to the login form description.
        """
        if current_provider and enterprise_customer_for_request(get_current_request()):
            log.info(
                "LoginFormEnterpriseOverrides running: provider=%s",
                getattr(current_provider, 'provider_id', None),
            )
            pipeline_kwargs = running_pipeline.get('kwargs')

            # Details about the user sent back from the provider.
            details = pipeline_kwargs.get('details')
            email = details.get('email', '')

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

    Only invoked while a third-party-auth pipeline is running (the platform triggers the
    filter exclusively from within its third-party-auth overrides). When the TPA Provider
    is configured to skip the registration form and we are in an enterprise context, we
    need to hide all fields except for terms of service and ensure that the user
    explicitly checks that field.

    The platform iterates its known registration fields and skips any without a provider
    override; this step iterates the provider overrides directly, which is equivalent
    because providers only return values for standard registration fields.
    """

    def run_filter(  # pylint: disable=arguments-differ
        self,
        form_desc: FormDescriptionProtocol,
        running_pipeline: dict,
        current_provider: ProviderConfigProtocol | None,
    ) -> dict[str, Any]:
        """
        Hide provider-prefilled registration fields (except terms of service) for
        enterprise SSO registrations.
        """
        if (
                current_provider
                and current_provider.skip_registration_form
                and enterprise_customer_for_request(get_current_request())
        ):
            log.info(
                "RegistrationFormEnterpriseOverrides running: provider=%s",
                getattr(current_provider, 'provider_id', None),
            )
            field_overrides = current_provider.get_register_form_data(
                running_pipeline.get('kwargs')
            )

            for field_name, field_default in field_overrides.items():
                # If SAML provider config has skip_registration_optional_checkboxes=True,
                # don't hide the marketing_emails_opt_in field (matching the platform's
                # guard around provider overrides for that field).
                #
                # NOTE: [2026-07-22] This new logic to derive skip_registration_optional_checkboxes
                # is technically different than the legacy platform logic. Historically,
                # current_provider was ignored and a *possibly different* provider config was looked
                # up by directly querying the database. Most or all of the time, that looked-up
                # provider config was the same as current_provider, but it was technically possible
                # for it to be different (e.g., the looked-up provider config happened to be a
                # disabled version). The new logic below is arguably more correct (and far simpler)
                # because we make no effort to re-lookup the provider config. We just use the
                # config already in-use by the current TPA pipeline.
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


class EnterpriseMFERedirectVeto(PipelineStep):
    """
    Keep enterprise learners on the legacy logistration page.

    Raises PreventRedirect when the request is associated with an enterprise customer, so
    that the enterprise-branded legacy login/registration page is rendered instead of
    redirecting to the authn micro-frontend.
    """

    def run_filter(self, request: Any) -> dict[str, Any]:  # pylint: disable=arguments-differ
        """
        Prevent the authn MFE redirect for enterprise customer requests.
        """
        if enterprise_customer_for_request(request):
            raise LogistrationMFERedirectRequested.PreventRedirect(
                'The logistration page must be rendered with enterprise customer content.'
            )
        return {'request': request}


class PostLoginEnterpriseRedirect(PipelineStep):
    """
    Updates redirect url to enterprise selection page if user is associated
    with multiple enterprises otherwise return the next url.
    """

    def run_filter(  # pylint: disable=arguments-differ
        self, redirect_url: str, user: Any, next_url: str,
    ) -> dict[str, Any]:
        """
        Return enterprise selection page URL if user is associated with multiple enterprises.
        """
        response = get_enterprise_learner_data_from_api(user)
        if response and len(response) > 1:
            log.info(
                "PostLoginEnterpriseRedirect running: user_id=%s linked to %s enterprises",
                user.id,
                len(response),
            )
            redirect_url = reverse('enterprise_select_active') + '/?success_url=' + urllib.parse.quote(next_url)

            # Check to see if next url has an enterprise in it. In this case if user is associated with
            # that enterprise, activate that enterprise and bypass the selection page.
            if re.match(_enterprise_enrollment_url_regex(), urllib.parse.unquote(next_url)):
                enterprise_in_url = re.search(UUID4_REGEX, next_url).group(0)
                for enterprise in response:
                    if enterprise_in_url == str(enterprise['enterprise_customer']['uuid']):
                        is_activated_successfully = activate_learner_enterprise(
                            get_current_request(), user, enterprise_in_url,
                        )
                        if is_activated_successfully:
                            redirect_url = next_url
                        break

        return {'redirect_url': redirect_url, 'user': user, 'next_url': next_url}
