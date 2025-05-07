"""
API client to communicate with SAP SuccessFactors services.
"""
import logging
import time
from urllib.parse import urljoin

import requests
from rest_framework.exceptions import APIException as DRFAPIException

from django.conf import settings
from django.core.cache import cache

LOGGER = logging.getLogger(__name__)

# Default timeout for cache if expires_in is not provided or too short (in seconds)
DEFAULT_CACHE_TIMEOUT_SECONDS = 5 * 60  # 5 minutes
# Buffer to subtract from expires_in to avoid using token right at expiry (in seconds)
CACHE_EXPIRY_BUFFER_SECONDS = 5 * 60  # 5 minutes
# Minimum cache timeout if expires_in is very short
MINIMUM_CACHE_TIMEOUT_SECONDS = 1 * 60 # 1 minute


class ClientError(DRFAPIException):
    """
    Exception for errors when calling SAP SuccessFactors API.
    """
    pass


class SAPSuccessFactorsClient:
    """
    Client for communicating with SAP SuccessFactors API.

    Handles user details retrieval via the OAuth/SAML authentication flow.
    """

    def __init__(self, enterprise_customer):
        """
        Initialize the SAP client with the enterprise customer.

        Args:
            enterprise_customer (EnterpriseCustomer): The enterprise customer with SSO configuration
        """
        self.enterprise_customer = enterprise_customer
        self.config = self._get_sso_config()

    def _get_sso_config(self):
        """
        Get the SSO configuration for the enterprise customer.
        
        Returns:
            EnterpriseCustomerSsoConfiguration: The SSO config for the enterprise customer
        """
        sso_configs = self.enterprise_customer.sso_orchestration_records.filter(
            identity_provider='sap_success_factors',
            active=True
        )
        if not sso_configs.exists():
            msg = f"No active SAP SSO configuration found for enterprise customer: {self.enterprise_customer.uuid}"
            LOGGER.error(msg)
            raise ClientError(msg)
        
        return sso_configs.first()
    
    def _get_cache_key(self):
        """
        Get the cache key for the SAP SSO token.
        
        Returns:
            str: The cache key
        """
        return f"sap_sso_token:{self.enterprise_customer.uuid}:{self.config.oauth_user_id}"
    
    def _invalidate_cached_token(self):
        cache_key = self._get_cache_key()
        cache.delete(cache_key)
        LOGGER.info(f"Invalidated token in cache (key: {cache_key}).")
        print(f"DEBUG: Invalidated token in cache: {cache_key}")

    def _get_saml_assertion(self):
        """
        Retrieve the SAML assertion from the IDP endpoint.

        Args:
            logged_in_user_id (str): The SAP user ID.

        Returns:
            str: The SAML assertion.

        Raises:
            ClientError: If the request fails or returns an error status.
        """
        idp_url = urljoin(self.config.sapsf_oauth_root_url, 'idp')
        token_url = urljoin(self.config.sapsf_oauth_root_url, 'token')

        idp_payload = {
            'client_id': self.config.odata_client_id,
            'user_id': self.config.oauth_user_id,
            'token_url': token_url,
            'private_key': self.config.sapsf_private_key
        }

        LOGGER.info(
            f"Requesting SAML assertion for user {self.config.oauth_user_id} from {idp_url}"
        )

        start_time = time.time()
        try:
            response = requests.post(
                idp_url,
                data=idp_payload,
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=self.config.odata_api_request_timeout
            )
            duration_seconds = time.time() - start_time

            LOGGER.info(f"SAML request for {self.config.oauth_user_id} completed in {duration_seconds:.2f}s, status {response.status_code}")

            response.raise_for_status()

            saml_assertion = response.text.strip('"')
            return saml_assertion

        except requests.HTTPError as e:
            error_message = f"SAML HTTPError for {self.config.oauth_user_id}: {e.response.status_code}, {e.response.text}"
            LOGGER.error(error_message)
            raise ClientError(error_message, status_code=e.response.status_code) from e
        except requests.RequestException as e:
            error_message = f"SAML RequestException for {self.config.oauth_user_id}: {e}"
            LOGGER.exception(error_message)
            raise ClientError(error_message) from e

    def _get_access_token(self, saml_assertion):
        """
        Exchange the SAML assertion for an OAuth access token.

        Args:
            saml_assertion (str): The SAML assertion obtained from the IDP.

        Returns:
            str: The OAuth access token.

        Raises:
            ClientError: If the request fails or returns an error status.
        """
        token_url = urljoin(self.config.sapsf_oauth_root_url, 'token')
        token_payload = {
            'grant_type': 'urn:ietf:params:oauth:grant-type:saml2-bearer',
            'assertion': saml_assertion,
            'client_id': self.config.odata_client_id,
            'company_id': self.config.odata_company_id,
            'api_key': self.config.odata_client_id
        }

        LOGGER.info(f"Exchanging SAML assertion for access token at {token_url}")

        start_time = time.time()
        try:
            response = requests.post(
                token_url,
                data=token_payload,
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=self.config.odata_api_request_timeout
            )
            duration_seconds = time.time() - start_time

            LOGGER.info(
                f"Token exchange completed in {duration_seconds:.2f}s with status {response.status_code}"
            )

            response.raise_for_status()

            token_data = response.json()
            access_token = token_data.get('access_token', '').strip('"')
            if not access_token:
                error_message = f"Access token not found in response: {token_data}"
                LOGGER.error(error_message)
                raise ClientError(error_message)
            
            expires_in = token_data.get('expires_in') # In seconds
            if expires_in is not None:
                try:
                    expires_in = int(expires_in)
                except ValueError:
                    LOGGER.warning(f"Could not parse expires_in value: {expires_in}. Using None.")
                    expires_in = None
            
            return access_token, expires_in

        except requests.HTTPError as e:
            error_message = f"Exchanging SAML for token HTTPError for {self.config.oauth_user_id}: {e.response.status_code}, {e.response.text}"
            LOGGER.error(error_message)
            raise ClientError(error_message, status_code=e.response.status_code) from e
        except requests.RequestException as e:
            error_message = f"Exchanging SAML for token RequestException for {self.config.oauth_user_id}: {e}"
            LOGGER.exception(error_message)
            raise ClientError(error_message) from e

    def _get_cached_access_token(self):
        """
        Get a cached access token if available, otherwise fetch a new one.
        
        Returns:
            str: The access token
        """
        cache_key = self._get_cache_key()
        cached_token = cache.get(cache_key)
        if cached_token:
            LOGGER.info(f"Using token from cache (key: {cache_key}).")
            print(f"DEBUG: Using token from cache: {cache_key}")
            return cached_token

        LOGGER.info(f"Token not in cache (key: {cache_key}). Fetching new.")
        print(f"DEBUG: Token not in cache: {cache_key}. Fetching new.")
        saml_assertion = self._get_saml_assertion()
        access_token, expires_in_seconds = self._get_access_token(saml_assertion)

        calculated_timeout = DEFAULT_CACHE_TIMEOUT_SECONDS
        if expires_in_seconds is not None:
            if expires_in_seconds > CACHE_EXPIRY_BUFFER_SECONDS:
                calculated_timeout = expires_in_seconds - CACHE_EXPIRY_BUFFER_SECONDS
            else:
                calculated_timeout = max(expires_in_seconds // 2, MINIMUM_CACHE_TIMEOUT_SECONDS)
        
        cache.set(cache_key, access_token, timeout=calculated_timeout)
        LOGGER.info(f"New token fetched and cached (key: {cache_key}, timeout: {calculated_timeout}s).")
        print(f"DEBUG: New token cached: {cache_key}, timeout: {calculated_timeout}s.")
        return access_token

    def fetch_user_details_odata(self, logged_in_user_id):
        """
        Retrieve user details from SAP SuccessFactors using a 3-step OAuth process.
        
        Makes three API calls to SAP (via helper methods):
        1. Get SAML Assertion
        2. Exchange for Access Token
        3. Call OData User endpoint
        
        Args:
            logged_in_user_id (str): The SAP user ID of the logged-in user
            
        Returns:
            dict: User data from SAP including email, name, etc.
        """
        access_token = self._get_cached_access_token()

            # Inlined _fetch_user_details_odata logic:
        user_url = urljoin(
            self.config.odata_api_root_url,
            f"User(userId='{logged_in_user_id}')?$select=userId,username,firstName,lastName,defaultFullName,email,country,city&$format=json"
        )
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json'
        }

        LOGGER.info(f"Requesting user details from {user_url}")

        start_time = time.time()
        try:
            response = requests.get(
                user_url,
                headers=headers,
                timeout=self.config.odata_api_request_timeout
            )
            duration_seconds = time.time() - start_time
            
            LOGGER.info(
                f"User details request completed in {duration_seconds:.2f}s with status {response.status_code}"
            )

            response.raise_for_status()
            
            user_data = response.json()
            return user_data
        
        except requests.HTTPError as e:
            error_message = f"Fetching user details odata HTTPError for {self.config.oauth_user_id}: {e.response.status_code}, {e.response.text}"
            LOGGER.error(error_message)
            if "LGN0007" in response.text:
                self._invalidate_cached_token()
            raise ClientError(error_message, status_code=e.response.status_code) from e
        except requests.RequestException as e:
            error_message = f"Fetching user details odata RequestException for {self.config.oauth_user_id}: {e}"
            LOGGER.exception(error_message)
            raise ClientError(error_message) from e