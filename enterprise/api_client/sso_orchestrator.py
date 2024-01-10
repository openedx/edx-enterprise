"""
Api client for the SSO Orchestrator API.
"""
from urllib.parse import urljoin

import requests
from edx_rest_api_client.client import get_request_id, user_agent
from requests.auth import HTTPBasicAuth
from requests.exceptions import RequestException
from rest_framework.reverse import reverse

from django.conf import settings

from enterprise.utils import (
    get_configuration_value,
    get_sso_orchestrator_api_base_url,
    get_sso_orchestrator_basic_auth_password,
    get_sso_orchestrator_basic_auth_username,
    get_sso_orchestrator_configure_edx_oauth_path,
    get_sso_orchestrator_configure_path,
)

USER_AGENT = user_agent()


class SsoOrchestratorClientError(RequestException):
    """
    Indicate a problem when interacting with an enterprise api client.
    """


class EnterpriseSSOOrchestratorApiClient:
    """
    The enterprise API client to communicate with the SSO Orchestrator API. Reads conf settings values to determine
    orchestration paths and credentials.

    Required settings values:
    - LMS_ROOT_URL
    - SSO_ORCHESTRATOR_API_BASE_URL
    - SSO_ORCHESTRATOR_CONFIGURE_PATH
    - SSO_ORCHESTRATOR_BASIC_AUTH_USERNAME
    - SSO_ORCHESTRATOR_BASIC_AUTH_PASSWORD
    """

    def __init__(self):
        self.base_url = get_sso_orchestrator_api_base_url()
        self.session = None

    def _get_orchestrator_callback_url(self, config_pk):
        """
        get the callback url for the SSO Orchestrator API
        """
        lms_base_url = get_configuration_value('LMS_ROOT_URL', settings.LMS_ROOT_URL)
        if not lms_base_url:
            raise SsoOrchestratorClientError(
                "Failed to create SSO Orchestrator callback url: LMS_ROOT_URL required.",
            )
        path = reverse(
            'enterprise-customer-sso-configuration-orchestration-complete',
            kwargs={'configuration_uuid': config_pk},
        )
        return urljoin(lms_base_url, path)

    def _get_orchestrator_configure_url(self):
        """
        get the configure url for the SSO Orchestrator API
        """
        # probably want config value validated for this
        return urljoin(self.base_url, get_sso_orchestrator_configure_path())

    def _get_orchestrator_configure_edx_oauth_url(self):
        """
        get the configure-edx-oauth url for the SSO Orchestrator API
        """
        if path := get_sso_orchestrator_configure_edx_oauth_path():
            return urljoin(self.base_url, path)
        return None

    def _create_auth_header(self):
        """
        create the basic auth header for requests to the SSO Orchestrator API
        """
        if orchestrator_username := get_sso_orchestrator_basic_auth_username():
            if orchestrator_password := get_sso_orchestrator_basic_auth_password():
                return HTTPBasicAuth(orchestrator_username, orchestrator_password)
            else:
                raise SsoOrchestratorClientError(
                    "Failed to create SSO Orchestrator auth headers: password required.",
                )
        raise SsoOrchestratorClientError(
            "Failed to create SSO Orchestrator auth headers: username required.",
        )

    def _create_session(self):
        """
        create a requests session object
        """
        if not self.session:
            self.session = requests.Session()
            self.session.headers['User-Agent'] = USER_AGENT
            self.session.headers['X-Request-ID'] = get_request_id()

    def _post(self, url, data=None):
        """
        make a POST request to the SSO Orchestrator API
        """
        self._create_session()
        response = self.session.post(url, json=data, auth=self._create_auth_header())
        if response.status_code >= 300:
            raise SsoOrchestratorClientError(
                (
                    f"Failed to make SSO Orchestrator API request: {response.status_code}\n"
                    f"{response.content}"
                ),
                response=response,
            )
        return response.json()

    def configure_sso_orchestration_record(
        self,
        config_data,
        config_pk,
        enterprise_data,
        is_sap=False,
        updating_existing_record=False,
        sap_config_data=None,
    ):
        """
        configure an SSO orchestration record
        """
        config_data['uuid'] = str(config_data['uuid'])
        request_data = {
            'samlConfiguration': config_data,
            'requestIdentifier': str(config_pk),
            'enterprise': enterprise_data,
        }

        callback_url = self._get_orchestrator_callback_url(str(config_pk))
        if updating_existing_record:
            callback_url = f"{callback_url}?updating_existing_record=true"
        request_data['callbackUrl'] = callback_url

        if is_sap or sap_config_data:
            request_data['sapsfConfiguration'] = sap_config_data

        response = self._post(self._get_orchestrator_configure_url(), data=request_data)
        return response.get('samlServiceProviderInformation', {}).get('spMetadataUrl', {})

    def configure_edx_oauth(self, enterprise_customer):
        """
        Configure SSO to GetSmarter using edX credentials via Auth0.

        Args:
            enterprise_customer (EnterpriseCustomer): The enterprise customer for which to configure edX OAuth.

        Returns:
            str: Auth0 Organization ID.

        Raises:
            SsoOrchestratorClientError: If the request to the SSO Orchestrator API failed.
        """
        request_data = {
            'enterpriseName': enterprise_customer.name,
            'enterpriseSlug': enterprise_customer.slug,
            'enterpriseUuid': str(enterprise_customer.uuid),
        }
        response = self._post(self._get_orchestrator_configure_edx_oauth_url(), data=request_data)
        return response.get('orgId', None)
