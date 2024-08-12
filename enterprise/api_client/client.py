"""
Base API clients to communicate with edx services.
"""
import logging
from functools import wraps
from time import time
from urllib.parse import urljoin

import requests
from edx_rest_api_client.auth import SuppliedJwtAuth
from edx_rest_api_client.client import OAuthAPIClient

from django.apps import apps
from django.conf import settings

from enterprise.utils import NotConnectedToOpenEdX  # pylint: disable=cyclic-import

try:
    from openedx.core.djangoapps.oauth_dispatch import jwt as JwtBuilder
except ImportError:
    JwtBuilder = None


LOGGER = logging.getLogger(__name__)


class APIClientMixin:
    """
    API client mixin.
    """
    APPEND_SLASH = False
    API_BASE_URL = ""

    def get_api_url(self, path, append_slash=None):
        """
        Helper method to construct the API URL.

        Args:
            path (str): the API endpoint path string.
        """
        _APPEND_SLASH = self.APPEND_SLASH if append_slash is None else append_slash
        return urljoin(f"{self.API_BASE_URL}/", f"{path.strip('/')}{'/' if _APPEND_SLASH else ''}")


class BackendServiceAPIClient(APIClientMixin):
    """
    API client based on OAuthAPIClient to communicate with edx services.

    Uses the backend service user to make requests.
    """
    def __init__(self):
        app_config = apps.get_app_config("enterprise")
        self.client = OAuthAPIClient(
            app_config.backend_service_edx_oauth2_provider_url,
            app_config.backend_service_edx_oauth2_key,
            app_config.backend_service_edx_oauth2_secret
        )


class UserAPIClient(APIClientMixin):
    """
    API client based on requests.Session to communicate with edx services.

    Requires user object to instantiate the client with the jwt token authentication.
    """
    def __init__(self, user, expires_in=settings.OAUTH_ID_TOKEN_EXPIRATION):
        self.user = user
        self.expires_in = expires_in
        self.expires_at = 0
        self.client = None

    def connect(self):
        """
        Connect to the REST API, authenticating with a JWT for the current user.
        """
        if JwtBuilder is None:
            raise NotConnectedToOpenEdX("This package must be installed in an OpenEdX environment.")

        now = time()
        jwt = JwtBuilder.create_jwt_for_user(self.user)
        self.client = requests.Session()
        self.client.auth = SuppliedJwtAuth(jwt)
        self.expires_at = now + self.expires_in

    def token_is_expired(self):
        """
        Return True if the JWT token has expired, False if not.
        """
        return time() > self.expires_at

    @staticmethod
    def refresh_token(func):
        """
        Use this method decorator to ensure the JWT token is refreshed when needed.
        """
        @wraps(func)
        def inner(self, *args, **kwargs):
            """
            Before calling the wrapped function, we check if the JWT token is expired, and if so, re-connect.
            """
            if self.token_is_expired():
                self.connect()
            return func(self, *args, **kwargs)
        return inner


class NoAuthAPIClient(APIClientMixin):
    """
    API client based on requests.Session to communicate with edx services.

    Used to call APIs which don't require authentication.
    """
    def __init__(self):
        self.client = requests.Session()

    def get_health(self):
        """
        Retrieve health details for the service.

        Returns:
            dict: Response containing the service health.
        """
        api_url = self.get_api_url("health")
        response = self.client.get(api_url)
        response.raise_for_status()
        return response.json()
