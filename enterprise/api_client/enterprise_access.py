"""
Client for communicating with the enterprise-access api
"""
from logging import getLogger
from urllib.parse import urljoin

from requests.exceptions import RequestException, Timeout

from django.conf import settings

from enterprise import utils
from enterprise.api_client.client import UserAPIClient

LOGGER = getLogger(__name__)


class EnterpriseAccessClientError(RequestException):
    """
    Indicate a problem when interacting with an enterprise access api client.
    """


class EnterpriseAccessApiClient(UserAPIClient):
    """
    The API client to make calls to the enterprise-access API.
    """

    API_BASE_URL = urljoin(f"{settings.ENTERPRISE_ACCESS_INTERNAL_ROOT_URL}/", "api/v1/")
    DELETE_ASSOCIATION_ENDPOINT = '{}/delete-group-association/{}'

    def __init__(self, user=None):
        user = user if user else utils.get_enterprise_worker_user()
        super().__init__(user)

    @UserAPIClient.refresh_token
    def delete_policy_group_association(self, enterprise_uuid, group_uuid):
        """
        Endpoint to connect to enterprise-access so we can delete any PolicyGroupAssocations after the
        deletion of an EnterpriseGroup
        """
        api_url = self.API_BASE_URL + self.DELETE_ASSOCIATION_ENDPOINT.format(enterprise_uuid, group_uuid)
        try:
            response = self.client.delete(api_url)
            response.raise_for_status()
            return 204 == response.status_code
        except (RequestException, Timeout) as exc:
            LOGGER.exception(
                'Failed to fetch any PolicyGroupAssociation from group %s due to [%s]',
                group_uuid, str(exc)
            )
            return {}
