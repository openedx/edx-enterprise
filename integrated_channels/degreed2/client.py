# -*- coding: utf-8 -*-
"""
Client for connecting to Degreed2.
"""

import json
import logging
import time

import requests
from six.moves.urllib.parse import urljoin

from django.apps import apps
from django.conf import settings
from django.http.request import QueryDict

from integrated_channels.exceptions import ClientError
from integrated_channels.integrated_channel.client import IntegratedChannelApiClient
from integrated_channels.utils import generate_formatted_log, refresh_session_if_expired

LOGGER = logging.getLogger(__name__)


class Degreed2APIClient(IntegratedChannelApiClient):
    """
    Client for connecting to Degreed2.

    Specifically, this class supports obtaining access tokens and posting to the courses and
    completion status endpoints.
    """

    CONTENT_WRITE_SCOPE = "content:write"
    ALL_DESIRED_SCOPES = "content:read,content:write,completions:write,completions:read"
    SESSION_TIMEOUT = getattr(settings, "ENTERPRISE_DEGREED2_SESSION_TIMEOUT", 60)
    MAX_RETRIES = getattr(settings, "ENTERPRISE_DEGREED2_MAX_RETRIES", 4)
    BACKOFF_FACTOR = getattr(settings, "ENTERPRISE_DEGREED2_BACKOFF_FACTOR", 2)

    def __init__(self, enterprise_configuration):
        """
        Instantiate a new client.

        Args:
            enterprise_configuration (Degreed2EnterpriseCustomerConfiguration): An enterprise customers's
            configuration model for connecting with Degreed
        """
        super().__init__(enterprise_configuration)
        self.session = None
        self.expires_at = None
        app_config = apps.get_app_config('degreed2')
        self.oauth_api_path = app_config.oauth_api_path
        self.courses_api_path = app_config.courses_api_path
        self.completions_api_path = app_config.completions_api_path
        # to log without having to pass channel_name, ent_customer_uuid each time
        self.make_log_msg = lambda course_key, message, lms_user_id=None: generate_formatted_log(
            self.enterprise_configuration.channel_code(),
            self.enterprise_configuration.enterprise_customer.uuid,
            lms_user_id,
            course_key,
            message,
        )

    def get_oauth_url(self):
        config = self.enterprise_configuration
        base_url = config.degreed_token_fetch_base_url or config.degreed_base_url
        return urljoin(base_url, self.oauth_api_path)

    def get_courses_url(self):
        return urljoin(self.enterprise_configuration.degreed_base_url, self.courses_api_path)

    def get_completions_url(self):
        return urljoin(self.enterprise_configuration.degreed_base_url, self.completions_api_path)

    def create_assessment_reporting(self, user_id, payload):
        """
        Not implemented yet.
        """
        LOGGER.error(
            generate_formatted_log(
                self.enterprise_configuration.channel_code(),
                self.enterprise_configuration.enterprise_customer.uuid,
                None,
                None,
                "Degreed2 integrated channel does not yet support assessment reporting."
            )
        )

    def cleanup_duplicate_assignment_records(self, courses):
        """
        Not implemented yet.
        """
        LOGGER.error(
            generate_formatted_log(
                self.enterprise_configuration.channel_code(),
                self.enterprise_configuration.enterprise_customer.uuid,
                None,
                None,
                "Degreed2 integrated channel does not yet support assignment deduplication."
            )
        )

    def create_course_completion(self, user_id, payload):
        """
        Completions status for a learner
        Ref: https://api.degreed.com/docs/#create-a-new-completion

        Arguments:
            - user_id: learner's id
            - payload: (dict) with keys:
                 {
                     degreed_user_email,
                     course_id,
                     completed_timestamp, (in the format "2018-08-01T00:00:00")
                 }
        Returns: status_code, response_text
        """
        json_payload = json.loads(payload)
        LOGGER.info(self.make_log_msg(
            json_payload.get('data').get('attributes').get('content-id'),
            f'Attempting find course via url: {self.get_completions_url()}'),
            user_id
        )
        return self._post(
            self.get_completions_url(),
            json_payload,
            self.ALL_DESIRED_SCOPES
        )

    def delete_course_completion(self, user_id, payload):
        """
        Not implemented yet. deletion requires completion ID. We don't have a way to get the ID right now.
        So we may need to store id on our side to be able to do this.
        https://api.degreed.com/docs/#delete-a-specific-completion
        """
        LOGGER.error(
            generate_formatted_log(
                self.enterprise_configuration.channel_code(),
                self.enterprise_configuration.enterprise_customer.uuid,
                None,
                None,
                "Degreed2 integrated channel does not yet support deleting course completions."
            )
        )

    def fetch_degreed_course_id(self, external_id):
        """
        Fetch the 'id' of a course from Degreed2, given the external-id as a search param
        'external-id' is the edX course key
        """
        # QueryDict converts + to space
        params = QueryDict(f"filter[external_id]={external_id.replace('+','%2B')}")
        course_search_url = f'{self.get_courses_url()}?{params.urlencode(safe="[]")}'
        LOGGER.info(self.make_log_msg(external_id, f'Attempting find course via url: {course_search_url}'))
        status_code, response_body = self._get(
            course_search_url,
            self.ALL_DESIRED_SCOPES
        )
        if status_code >= 400:
            raise ClientError(
                f'Degreed2: fetch request failed: attempted, external ID={external_id},'
                f'received status_code={status_code}',
                status_code=status_code
            )
        response_json = json.loads(response_body)
        if response_json['data']:
            return response_json['data'][0]['id']
        raise ClientError(
            f'Degreed2: Attempted to find degreed course id but failed, external id was {external_id}'
            f', Response from Degreed was {response_body}')

    def create_content_metadata(self, serialized_data):
        """
        Create content metadata using the Degreed course content API.

        Args:
            serialized_data: JSON-encoded object containing content metadata.

        Raises:
            ClientError: If Degreed API request fails.
        """
        channel_metadata_item = json.loads(serialized_data.decode('utf-8'))
        # only expect one course in this array as of now (chunk size is 1)
        a_course = channel_metadata_item['courses'][0]
        status_code, response_body = self._sync_content_metadata(a_course, 'post', self.get_courses_url())
        if status_code == 409:
            # course already exists, don't raise failure, but log and move on
            LOGGER.warning(
                self.make_log_msg(
                    a_course.get('external-id'),
                    f'Course with integration_id = {a_course.get("external-id")} already exists, '
                )
            )
            # content already exists, we'll treat this as a success
            status_code = 200
        elif status_code >= 400:
            raise ClientError(
                f'Degreed2APIClient create_content_metadata failed with status {status_code}: {response_body}',
                status_code=status_code
            )
        return status_code, response_body

    def update_content_metadata(self, serialized_data):
        """
        Update content metadata using the Degreed course content API.

        Args:
            serialized_data: JSON-encoded object containing content metadata.

        Raises:
            ClientError: If Degreed API request fails.
        """
        channel_metadata_item = json.loads(serialized_data.decode('utf-8'))
        course_item = channel_metadata_item['courses'][0]
        external_id = course_item.get('external-id')

        course_id = self.fetch_degreed_course_id(external_id)
        if not course_id:
            raise ClientError(f'Degreed2: Cannot find course via external-id {external_id}')

        patch_url = f'{self.get_courses_url()}/{course_id}'
        LOGGER.info(self.make_log_msg(external_id, f'Attempting course update via {patch_url}'))
        patch_status_code, patch_response_body = self._sync_content_metadata(
            course_item,
            'patch',
            patch_url,
            course_id
        )
        return patch_status_code, patch_response_body

    def delete_content_metadata(self, serialized_data):
        """
        Delete content metadata using the Degreed course content API.

        Args:
            serialized_data: JSON-encoded object containing content metadata.

        Raises:
            ClientError: If Degreed API request fails.
        """
        # {{base_api_url}}/api/v2/content/courses?filter[external_id]=course-v1%3AedX%2B444555666%2B3T2021
        channel_metadata_item = json.loads(serialized_data.decode('utf-8'))
        course_item = channel_metadata_item['courses'][0]
        external_id = course_item.get('external-id')

        del_status_code = None
        del_response_body = ''
        try:
            course_id = self.fetch_degreed_course_id(external_id)
            if not course_id:
                raise ClientError(f'Degreed2: Cannot find course via external-id {external_id}')

            del_url = f'{self.get_courses_url()}/{course_id}'
            LOGGER.info(self.make_log_msg(external_id, f'Attempting course delete via {del_url}'))
            del_status_code, del_response_body = self._delete(
                del_url,
                None,
                self.ALL_DESIRED_SCOPES
            )
            if del_status_code >= 400:
                raise ClientError(
                    f'Degreed2: delete request failed: attempted, external ID={external_id},'
                    f'status_code={del_status_code}'
                    f'response_body={del_response_body}',
                    status_code=del_status_code
                )
        except requests.exceptions.RequestException as exc:
            raise ClientError(
                'Degreed2APIClient delete request failed: {error} {message}'.format(
                    error=exc.__class__.__name__,
                    message=str(exc)
                )
            ) from exc

        return del_status_code, del_response_body

    def _sync_content_metadata(self, course_attributes, http_method, override_url, degreed_course_id=None):
        """
        Synchronize content metadata using the Degreed course content API.
        Invokes the Create/Update operations of degreed api
        Used for create course, and update course use cases
        The json sent contains

        Args:
            course_attributes: JSON object containing content metadata converted into
              Degreed2 'attributes' in the payload.
            http_method: The HTTP method to use for the API request.
            override_url: uses this url to post to
            course_id: used to append at the end of the url as /ID if provided

        Raises:
            ClientError: If Degreed API request fails.
        """
        json_to_send = {
            "data": {
                "type": "content/courses",
                "attributes": course_attributes,
            }
        }

        # useful for update use case
        if degreed_course_id:
            json_to_send['data']['id'] = degreed_course_id

        LOGGER.info(self.make_log_msg('', f'About to post payload: {json_to_send}'))
        try:
            status_code, response_body = getattr(self, '_' + http_method)(
                override_url,
                json_to_send,
                self.ALL_DESIRED_SCOPES
            )
        except requests.exceptions.RequestException as exc:
            raise ClientError(
                'Degreed2APIClient request failed: {error} {message}'.format(
                    error=exc.__class__.__name__,
                    message=str(exc)
                )
            ) from exc
        return status_code, response_body

    def _calculate_backoff(self, attempt_count):
        """
        Calcualte the seconds to sleep based on attempt_count
        """
        return (self.BACKOFF_FACTOR * (2 ** (attempt_count - 1)))

    def _get(self, url, scope):
        """
        Make a GET request using the session object to a Degreed2 endpoint.

        Args:
            url (str): The url to send a GET request to.
            scope (str): Must be one of the scopes Degreed expects:
                        - `CONTENT_WRITE_SCOPE`
                        - `CONTENT_READ_SCOPE`
        """
        self._create_session(scope)
        attempts = 0
        while True:
            attempts = attempts + 1
            response = self.session.get(url)
            if attempts <= self.MAX_RETRIES and response.status_code == 429:
                sleep_seconds = self._calculate_backoff(attempts)
                LOGGER.warning(
                    generate_formatted_log(
                        self.enterprise_configuration.channel_code(),
                        self.enterprise_configuration.enterprise_customer.uuid,
                        None,
                        None,
                        f'429 detected from {url}, backing-off before retrying, '
                        f'sleeping {sleep_seconds} seconds...'
                    )
                )
                time.sleep(sleep_seconds)
            else:
                break
        return response.status_code, response.text

    def _post(self, url, data, scope):
        """
        Make a POST request using the session object to a Degreed2 endpoint.

        Args:
            url (str): The url to send a POST request to.
            data (dict): The json payload to POST.
            scope (str): Must be one of the scopes Degreed expects:
                        - `CONTENT_WRITE_SCOPE`
                        - `CONTENT_READ_SCOPE`
        """
        self._create_session(scope)
        attempts = 0
        while True:
            attempts = attempts + 1
            response = self.session.post(url, json=data)
            if attempts <= self.MAX_RETRIES and response.status_code == 429:
                sleep_seconds = self._calculate_backoff(attempts)
                LOGGER.warning(
                    generate_formatted_log(
                        self.enterprise_configuration.channel_code(),
                        self.enterprise_configuration.enterprise_customer.uuid,
                        None,
                        None,
                        f'429 detected from {url}, backing-off before retrying, '
                        f'sleeping {sleep_seconds} seconds...'
                    )
                )
                time.sleep(sleep_seconds)
            else:
                break
        return response.status_code, response.text

    def _patch(self, url, data, scope):
        """
        Make a PATCH request using the session object to a Degreed2 endpoint.

        Args:
            url (str): The url to send a POST request to.
            data (str): The json payload to POST.
            scope (str): Must be one of the scopes Degreed expects:
                        - `CONTENT_WRITE_SCOPE`
                        - `CONTENT_READ_SCOPE`
        """
        self._create_session(scope)
        attempts = 0
        while True:
            attempts = attempts + 1
            response = self.session.patch(url, json=data)
            if attempts <= self.MAX_RETRIES and response.status_code == 429:
                sleep_seconds = self._calculate_backoff(attempts)
                LOGGER.warning(
                    generate_formatted_log(
                        self.enterprise_configuration.channel_code(),
                        self.enterprise_configuration.enterprise_customer.uuid,
                        None,
                        None,
                        f'429 detected from {url}, backing-off before retrying, '
                        f'sleeping {sleep_seconds} seconds...'
                    )
                )
                time.sleep(sleep_seconds)
            else:
                break
        return response.status_code, response.text

    def _delete(self, url, data, scope):
        """
        Make a DELETE request using the session object to a Degreed endpoint.

        Args:
            url (str): The url to send a DELETE request to.
            data (str): The json payload to DELETE. None means nothing is sent in payload.
            scope (str): Must be one of the scopes Degreed expects:
                        - `CONTENT_PROVIDER_SCOPE`
                        - `COMPLETION_PROVIDER_SCOPE`
        """
        self._create_session(scope)
        attempts = 0
        while True:
            attempts = attempts + 1
            response = self.session.delete(url, json=data) if data else self.session.delete(url)
            if attempts <= self.MAX_RETRIES and response.status_code == 429:
                sleep_seconds = self._calculate_backoff(attempts)
                LOGGER.warning(
                    generate_formatted_log(
                        self.enterprise_configuration.channel_code(),
                        self.enterprise_configuration.enterprise_customer.uuid,
                        None,
                        None,
                        f'429 detected from {url}, backing-off before retrying, '
                        f'sleeping {sleep_seconds} seconds...'
                    )
                )
                time.sleep(sleep_seconds)
            else:
                break
        return response.status_code, response.text

    def _create_session(self, scope):
        """
        Instantiate a new session object for use in connecting with Degreed
        """
        self.session, self.expires_at = refresh_session_if_expired(
            lambda: self._get_oauth_access_token(scope),
            self.session,
            self.expires_at,
        )

    def _get_oauth_access_token(self, scope):
        """ Retrieves OAuth 2.0 access token using the client credentials grant.
        Prefers using the degreed_token_fetch_base_url over the degreed_base_url, if present, to fetch the access token.

        Args:
            scope (str): Must be one or comma separated list of the scopes Degreed expects
        Returns:
            tuple: Tuple containing access token string and expiration datetime.
        Raises:
            HTTPError: If we received a failure response code from Degreed.
            ClientError: If an unexpected response format was received that we could not parse.
        """
        config = self.enterprise_configuration
        response = requests.post(
            self.get_oauth_url(),
            data={
                'grant_type': 'client_credentials',
                'scope': scope,
                'client_id': config.client_id,
                'client_secret': config.client_secret,
            },
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )

        try:
            data = response.json()
            return data['access_token'], data['expires_in']
        except (KeyError, ValueError) as error:
            raise ClientError(response.text, response.status_code) from error
