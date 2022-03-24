"""
Views containing APIs for Blackboard integrated channel
"""

import base64
import logging
from http import HTTPStatus
from urllib.parse import urljoin

import requests
from rest_framework import generics
from rest_framework.exceptions import NotFound
from rest_framework.renderers import JSONRenderer


from django.apps import apps
from django.conf import settings
from django.core.exceptions import ValidationError
from django.shortcuts import render

from enterprise.utils import get_enterprise_customer
from integrated_channels.blackboard.models import BlackboardEnterpriseCustomerConfiguration

LOGGER = logging.getLogger(__name__)


def log_auth_response(auth_token_url, data):
    """
    Logs the response from a refresh_token fetch.
    some fields may be absent in the response:
    ref: https://www.oauth.com/oauth2-servers/access-tokens/access-token-response/
    """
    scope = data['scope'] if 'scope' in data else 'not_found'
    user_id = data['user_id'] if 'user_id' in data else 'not_found'
    LOGGER.info("BLACKBOARD: response from {} contained: token_type={},"
                "expires_in={}, scope={}, user_id={}".format(
                    auth_token_url,
                    data['token_type'],
                    data['expires_in'],
                    scope,
                    user_id,
                ))


class BlackboardCompleteOAuthView(generics.ListAPIView):
    """
        **Use Cases**

            Retrieve and save a Blackboard OAuth refresh token after an enterprise customer
            authorizes to integrated courses. Typically for use to plug into the redirect_uri field
            in visiting the 'authorizationcode' endpoint:
            Ref: https://developer.blackboard.com/portal/displayApi/Learn
            e.g. https://blackboard.edx.us.org/learn/api/public/v1/oauth2/
                 authorizationcode?redirect_uri={{this_endpoint}}&response_type=code
                 &client_id={{app id}}&state={{blackboard_enterprise_customer_configuration.uuid}}

        **Example Requests**

            GET /blackboard/oauth-complete?code=123abc&state=abc123

        **Query Parameters for GET**

            * code: The one time use string generated by the Blackboard API used to fetch the
            access and refresh tokens for integrating with Blackboard.

            * state: The user's enterprise customer uuid used to associate the incoming
            code with an enterprise configuration model.

        **Response Values**

            HTTP 200 "OK" if successful

            HTTP 400 if code/state is not provided

            HTTP 404 if state is not valid or contained in the set of registered enterprises

    """
    renderer_classes = [JSONRenderer, ]

    def render_page(self, request, error):
        """
        Return a success or failure page based on Blackboard OAuth response
        """
        success_template = 'enterprise/admin/oauth_authorization_successful.html'
        error_template = 'enterprise/admin/oauth_authorization_failed.html'
        template = error_template if error else success_template

        return render(request, template, context={})

    def get(self, request, *args, **kwargs):
        app_config = apps.get_app_config('blackboard')
        oauth_token_path = app_config.oauth_token_auth_path

        # Check if encountered an error when generating the oauth code.
        request_error = request.GET.get('error')
        if request_error:
            LOGGER.error(
                "Blackboard OAuth API encountered an error when generating client code - "
                "error: {} description: {}".format(
                    request_error,
                    request.GET.get('error_description')
                )
            )
            return self.render_page(request, 'error')

        # Retrieve the newly generated code and state (Enterprise user's ID)
        client_code = request.GET.get('code')
        state_uuid = request.GET.get('state')

        if not state_uuid:
            LOGGER.error("Blackboard Configuration uuid (as 'state' url param) needed to obtain refresh token")
            return self.render_page(request, 'error')

        if not client_code:
            LOGGER.error("'code' url param was not provided, needed to obtain refresh token")
            return self.render_page(request, 'error')

        try:
            enterprise_config = BlackboardEnterpriseCustomerConfiguration.objects.get(uuid=state_uuid)
        except (BlackboardEnterpriseCustomerConfiguration.DoesNotExist, ValidationError):
            enterprise_config = None

        # old urls may use the enterprise customer uuid in place of the config uuid, so lets fallback
        if not enterprise_config:
            enterprise_customer = get_enterprise_customer(state_uuid)

            if not enterprise_customer:
                LOGGER.exception(f"No state data found for given uuid: {state_uuid}.")
                return self.render_page(request, 'error')

            try:
                enterprise_config = BlackboardEnterpriseCustomerConfiguration.objects.get(
                    enterprise_customer=enterprise_customer
                )
            except BlackboardEnterpriseCustomerConfiguration.DoesNotExist:
                LOGGER.exception(f"No Blackboard configuration found for state: {state_uuid}")
                return self.render_page(request, 'error')

        BlackboardGlobalConfiguration = apps.get_model(
            'blackboard',
            'BlackboardGlobalConfiguration'
        )
        blackboard_global_config = BlackboardGlobalConfiguration.current()
        if not blackboard_global_config:
            LOGGER.exception("No global Blackboard configuration found")
            return self.render_page(request, 'error')

        auth_header = self._create_auth_header(enterprise_config, blackboard_global_config)

        access_token_request_params = {
            'grant_type': 'authorization_code',
            'redirect_uri': settings.LMS_INTERNAL_ROOT_URL + "/blackboard/oauth-complete",
            'code': client_code,
        }

        auth_token_url = urljoin(enterprise_config.blackboard_base_url, oauth_token_path)

        auth_response = requests.post(
            auth_token_url,
            access_token_request_params,
            headers={
                'Authorization': auth_header,
                'Content-Type': 'application/x-www-form-urlencoded'
            })

        try:
            data = auth_response.json()
            if 'refresh_token' not in data:
                LOGGER.exception("BLACKBOARD: failed to find refresh_token in auth response. "
                                 "Auth response text: {}, Response code: {}, JSON response: {}".format(
                                     auth_response.text,
                                     auth_response.status_code,
                                     data,
                                 ))
                return self.render_page(request, 'error')

            log_auth_response(auth_token_url, data)
            refresh_token = data['refresh_token']
            if refresh_token.strip():
                enterprise_config.refresh_token = refresh_token
                enterprise_config.save()
            else:
                LOGGER.error("BLACKBOARD: Invalid/empty refresh_token! Cannot use it.")
                return self.render_page(request, 'error')
        except KeyError:
            LOGGER.exception("BLACKBOARD: failed to find required data in auth response. "
                             "Auth response text: {}, Response code: {}, JSON response: {}".format(
                                auth_response.text,
                                auth_response.status_code,
                                data,
                ))
            return self.render_page(request, 'error')
        except ValueError:
            LOGGER.exception("BLACKBOARD: auth response is invalid json. auth_response: {}".format(auth_response))
            return self.render_page(request, 'error')

        status = '' if auth_response.status_code == 200 else 'error'

        return self.render_page(request, status)

    def _create_auth_header(self, enterprise_config, blackboard_global_config):
        """
        Auth header in oauth2 token format as per Blackboard doc
        """
        app_key = enterprise_config.client_id
        if not app_key:
            if not blackboard_global_config.app_key:
                raise NotFound(
                    "Failed to generate oauth access token: Client ID required.",
                    HTTPStatus.INTERNAL_SERVER_ERROR.value
                )
            app_key = blackboard_global_config.app_key
        app_secret = enterprise_config.client_secret
        if not app_secret:
            if not blackboard_global_config.app_secret:
                raise NotFound(
                    "Failed to generate oauth access token: Client secret required.",
                    HTTPStatus.INTERNAL_SERVER_ERROR.value
                )
            app_secret = blackboard_global_config.app_secret
        return f"Basic {base64.b64encode(f'{app_key}:{app_secret}'.encode('utf-8')).decode()}"
