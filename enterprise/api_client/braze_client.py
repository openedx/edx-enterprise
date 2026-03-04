"""
Braze API client for campaign triggering and campaign management.
Provides methods to build recipients and send campaign messages to Braze.
"""
import logging
from typing import Any, Dict, List, Optional, Union

import requests
from braze.constants import BrazeAPIEndpoints
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

# Constants for configurability
DEFAULT_TIMEOUT = 30
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_FACTOR = 0.5
MAX_RECIPIENTS_PER_REQUEST = 50  # Braze recommended limit


class BrazeClientError(Exception):
    """Exception raised when Braze API requests fail."""

    def __init__(self, message: str, response: Optional[requests.Response] = None, status_code: Optional[int] = None):
        super().__init__(message)
        self.response = response
        self.status_code = status_code or (response.status_code if response else None)


class BrazeValidationError(Exception):
    """Exception raised when input validation fails."""


class BrazeAPIClient:
    """
    Optimized API client for Braze campaign triggering with retry logic and validation.

    Example::

        client = BrazeAPIClient(api_key, api_url)
        recipient = client.build_recipient("user_id", email="user@example.com")
        response = client.send_campaign_message(
            campaign_id="campaign_id",
            recipients=[recipient],
            trigger_properties={"key": "value"}
        )

    Args:
        api_key: Braze REST API key
        api_url: Braze REST API endpoint URL
        timeout: Request timeout in seconds (default: 30)
        max_retries: Maximum number of retry attempts (default: 3)
    """
    def __init__(
        self,
        api_key: str,
        api_url: str,
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES
    ):
        # Input validation
        if not isinstance(api_key, str) or not api_key:
            raise BrazeValidationError("api_key must be a non-empty string")
        if not isinstance(api_url, str) or not api_url:
            raise BrazeValidationError("api_url must be a non-empty string")

        self.api_key = api_key
        self.api_url = api_url.rstrip('/')
        self.timeout = timeout
        self.session = self._create_session(max_retries)

    def _create_session(self, max_retries: int) -> requests.Session:
        """
        Create a requests session with retry logic.

        Retries on:
        - 429 (Rate Limit)
        - 500, 502, 503, 504 (Server Errors)
        """
        session = requests.Session()
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=DEFAULT_BACKOFF_FACTOR,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def build_recipient(
        self,
        external_user_id: str,
        email: Optional[str] = None,
        send_to_existing_only: bool = False,
        attributes: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Build a recipient dict for Braze API with validation.

        Args:
            external_user_id: Unique identifier for the user
            email: User's email address
            send_to_existing_only: Only send to existing Braze users
            attributes: Additional user attributes

        Returns:
            Recipient dictionary for Braze API

        Raises:
            BrazeValidationError: If external_user_id is invalid
        """
        # Validate external_user_id
        if not isinstance(external_user_id, str) or not external_user_id:
            raise BrazeValidationError("external_user_id must be a non-empty string")

        recipient = {
            "external_user_id": external_user_id,
            "send_to_existing_only": send_to_existing_only
        }

        # Build attributes without mutating input
        attr = attributes.copy() if attributes else {}
        if email:
            attr["email"] = email
        if attr:
            recipient["attributes"] = attr

        return recipient

    def send_campaign_message(
        self,
        campaign_id: str,
        recipients: List[Union[Dict[str, Any], str]],
        trigger_properties: Optional[Dict[str, Any]] = None,
        broadcast: bool = False
    ) -> Dict[str, Any]:
        """
        Trigger a Braze campaign for recipients with validation and retry logic.

        Args:
            campaign_id: Braze campaign ID
            recipients: List of recipient dicts or email strings
            trigger_properties: Personalization properties
            broadcast: Send as broadcast

        Returns:
            Braze API response as dict

        Raises:
            BrazeValidationError: If input validation fails
            BrazeClientError: If the API request fails
        """
        # Input validation
        if not isinstance(campaign_id, str) or not campaign_id:
            raise BrazeValidationError("campaign_id must be a non-empty string")
        if not isinstance(recipients, list) or not recipients:
            raise BrazeValidationError("recipients must be a non-empty list")

        # Warn about large batches (Braze recommends max 50 per request)
        if len(recipients) > MAX_RECIPIENTS_PER_REQUEST:
            logger.warning(
                "Recipient count (%d) exceeds recommended limit (%d) for campaign %s",
                len(recipients),
                MAX_RECIPIENTS_PER_REQUEST,
                campaign_id
            )

        url = f"{self.api_url}{BrazeAPIEndpoints.SEND_CAMPAIGN}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # Build recipients list with clear error handling
        built_recipients = []
        for idx, r in enumerate(recipients):
            if isinstance(r, dict):
                built_recipients.append(r)
            elif isinstance(r, str):
                built_recipients.append(
                    self.build_recipient(
                        external_user_id=r,
                        email=r,
                        send_to_existing_only=False,
                        attributes={"email": r}
                    )
                )
            else:
                raise BrazeValidationError(f"Invalid recipient type at index {idx}: {type(r).__name__}")

        payload = {
            "campaign_id": campaign_id,
            "trigger_properties": trigger_properties or {},
            "recipients": built_recipients,
            "broadcast": broadcast
        }

        try:
            # Log count only, not email addresses (privacy/GDPR)
            logger.info(
                "Sending Braze campaign %s to %d recipients",
                campaign_id,
                len(recipients)
            )
            response = self.session.post(url, json=payload, headers=headers, timeout=self.timeout)
            response.raise_for_status()

            # Parse JSON response with error handling
            try:
                response_data = response.json()
            except ValueError as e:
                raise BrazeClientError(f"Invalid JSON response from Braze API: {e}", response=response) from e

            logger.info(
                "Successfully sent Braze campaign %s to %d recipients",
                campaign_id,
                len(recipients)
            )
            return response_data

        except requests.Timeout as e:
            error_msg = f"Braze API request timed out after {self.timeout}s: {e}"
            logger.error(error_msg)
            raise BrazeClientError(error_msg) from e
        except requests.HTTPError as e:
            error_msg = f"Braze API HTTP error: {e}"
            status_code = None
            if e.response is not None:
                status_code = e.response.status_code
                try:
                    error_detail = e.response.json()
                    error_msg += f" - Status: {status_code}, Detail: {error_detail}"
                except ValueError:
                    error_msg += f" - Status: {status_code}, Response: {e.response.text[:200]}"
            logger.error(error_msg)
            raise BrazeClientError(error_msg, response=e.response, status_code=status_code) from e
        except requests.RequestException as e:
            error_msg = f"Braze API request failed: {e}"
            logger.error(error_msg)
            raise BrazeClientError(error_msg) from e
