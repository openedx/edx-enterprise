# -*- coding: utf-8 -*-
"""
Client for connecting to SAP SuccessFactors.
"""

import datetime
import json
import logging
import time

import requests
from requests.exceptions import ConnectionError, Timeout  # pylint: disable=redefined-builtin

from django.apps import apps

from integrated_channels.exceptions import ClientError
from integrated_channels.integrated_channel.client import IntegratedChannelApiClient
from integrated_channels.utils import generate_formatted_log

LOGGER = logging.getLogger(__name__)

CONTENT_TYPE_APP_JSON = 'application/json'


class SAPSuccessFactorsAPIClient(IntegratedChannelApiClient):  # pylint: disable=abstract-method
    """
    Client for connecting to SAP SuccessFactors.

    Specifically, this class supports obtaining access tokens and posting to the courses and
     completion status endpoints.
    """

    SESSION_TIMEOUT = 5

    GENERIC_COURSE_COMPLETION_PATH = 'learning/odatav4/public/admin/learningevent-service/v1/OCNLearningEvents'

    @staticmethod
    def get_oauth_access_token(url_base, client_id, client_secret, company_id, user_id, user_type):
        """ Retrieves OAuth 2.0 access token using the client credentials grant.

        Args:
            url_base (str): Oauth2 access token endpoint
            client_id (str): client ID
            client_secret (str): client secret
            company_id (str): SAP company ID
            user_id (str): SAP user ID
            user_type (str): type of SAP user (admin or user)

        Returns:
            tuple: Tuple containing access token string and expiration datetime.
        Raises:
            HTTPError: If we received a failure response code from SAP SuccessFactors.
            ClientError: If an unexpected response format was received that we could not parse.
        """
        SAPSuccessFactorsGlobalConfiguration = apps.get_model(
            'sap_success_factors',
            'SAPSuccessFactorsGlobalConfiguration'
        )
        global_sap_config = SAPSuccessFactorsGlobalConfiguration.current()
        url = url_base + global_sap_config.oauth_api_path

        response = requests.post(
            url,
            json={
                'grant_type': 'client_credentials',
                'scope': {
                    'userId': user_id,
                    'companyId': company_id,
                    'userType': user_type,
                    'resourceType': 'learning_public_api',
                }
            },
            auth=(client_id, client_secret),
            headers={'content-type': CONTENT_TYPE_APP_JSON}
        )

        try:
            data = response.json()
            return data['access_token'], datetime.datetime.utcfromtimestamp(data['expires_in'] + int(time.time()))
        except (KeyError, TypeError, ValueError) as error:
            LOGGER.error(
                'SAP SF OAuth2 POST response is of invalid format. User: [%s], Company: [%s],'
                ' Error: [%s], Response: [%s]',
                str(user_id),
                str(company_id),
                str(error),
                str(response)
            )
            raise ClientError(response, response.status_code) from error

    def __init__(self, enterprise_configuration):
        """
        Instantiate a new client.

        Args:
            enterprise_configuration (SAPSuccessFactorsEnterpriseCustomerConfiguration): An enterprise customers's
            configuration model for connecting with SAP SuccessFactors
        """
        super().__init__(enterprise_configuration)
        self.global_sap_config = apps.get_model('sap_success_factors', 'SAPSuccessFactorsGlobalConfiguration').current()
        self.session = None
        self.expires_at = None

    def _create_session(self):
        """
        Instantiate a new session object for use in connecting with SAP SuccessFactors
        """
        now = datetime.datetime.utcnow()
        if self.session is None or self.expires_at is None or now >= self.expires_at:
            # Create a new session with a valid token
            if self.session:
                self.session.close()

            oauth_access_token, expires_at = SAPSuccessFactorsAPIClient.get_oauth_access_token(
                self.enterprise_configuration.sapsf_base_url,
                self.enterprise_configuration.key,
                self.enterprise_configuration.secret,
                self.enterprise_configuration.sapsf_company_id,
                self.enterprise_configuration.sapsf_user_id,
                self.enterprise_configuration.user_type
            )
            session = requests.Session()
            session.timeout = self.SESSION_TIMEOUT
            session.headers['Authorization'] = 'Bearer {}'.format(oauth_access_token)
            session.headers['content-type'] = CONTENT_TYPE_APP_JSON
            self.session = session
            self.expires_at = expires_at

    def create_assessment_reporting(self, user_id, payload):
        """
        Not implemented yet
        """

    def create_course_completion(self, user_id, payload):
        """
        Send a completion status payload to the SuccessFactors OCN Completion Status endpoint

        Args:
            user_id (str): The sap user id that the completion status is being sent for.
            payload (str): JSON encoded object (serialized from SapSuccessFactorsLearnerDataTransmissionAudit)
                containing completion status fields per SuccessFactors documentation.

        Returns:
            The body of the response from SAP SuccessFactors, if successful
        Raises:
            HTTPError: if we received a failure response code from SAP SuccessFactors
        """
        base_url = self.enterprise_configuration.sapsf_base_url

        if self.enterprise_configuration.prevent_self_submit_grades:
            # TODO:
            #   if/when we decide we should use the generic course completion path
            #   for all customers, we should update the _payload_data method on the
            #   SapSuccessFactorsLearnerDataTransmissionAudit class instead of doing this
            payload_to_update = json.loads(payload)
            payload_to_update['courseCompleted'] = bool(payload_to_update['courseCompleted'] == 'true')
            return self._call_post_with_session(
                base_url + self.GENERIC_COURSE_COMPLETION_PATH,
                json.dumps(payload_to_update)
            )

        return self._call_post_with_user_override(
            user_id,
            base_url + self.global_sap_config.completion_status_api_path,
            payload
        )

    def create_content_metadata(self, serialized_data):
        """
        Create content metadata records using the SuccessFactors OCN Course Import API endpoint.

        Arguments:
            serialized_data: Serialized JSON string representing a list of content metadata items.

        Raises:
            ClientError: If SuccessFactors API call fails.
        """
        self._sync_content_metadata(serialized_data)

    def update_content_metadata(self, serialized_data):
        """
        Update content metadata records using the SuccessFactors OCN Course Import API endpoint.

        Arguments:
            serialized_data: Serialized JSON string representing a list of content metadata items.

        Raises:
            ClientError: If SuccessFactors API call fails.
        """
        self._sync_content_metadata(serialized_data)

    def delete_content_metadata(self, serialized_data):
        """
        Delete content metadata records using the SuccessFactors OCN Course Import API endpoint.

        Arguments:
            serialized_data: Serialized JSON string representing a list of content metadata items.

        Raises:
            ClientError: If SuccessFactors API call fails.
        """
        self._sync_content_metadata(serialized_data)

    def _sync_content_metadata(self, serialized_data):
        """
        Create/update/delete content metadata records using the SuccessFactors OCN Course Import API endpoint.

        Arguments:
            serialized_data: Serialized JSON string representing a list of content metadata items.

        Raises:
            ClientError: If SuccessFactors API call fails.
        """
        url = self.enterprise_configuration.sapsf_base_url + self.global_sap_config.course_api_path
        try:
            status_code, response_body = self._call_post_with_session(url, serialized_data)
        except requests.exceptions.RequestException as exc:
            raise ClientError(
                'SAPSuccessFactorsAPIClient request failed: {error} {message}'.format(
                    error=exc.__class__.__name__,
                    message=str(exc)
                )
            ) from exc

        if status_code >= 400:
            raise ClientError(
                'SAPSuccessFactorsAPIClient request failed with status {status_code}: {message}'.format(
                    status_code=status_code,
                    message=response_body
                )
            )

    def _call_post_with_user_override(self, sap_user_id, url, payload):
        """
        Make a post request with an auth token acquired for a specific user to a SuccessFactors endpoint.

        Args:
            sap_user_id (str): The user to use to retrieve an auth token.
            url (str): The url to post to.
            payload (str): The json encoded payload to post.
        """
        SAPSuccessFactorsEnterpriseCustomerConfiguration = apps.get_model(
            'sap_success_factors',
            'SAPSuccessFactorsEnterpriseCustomerConfiguration'
        )
        oauth_access_token, _ = SAPSuccessFactorsAPIClient.get_oauth_access_token(
            self.enterprise_configuration.sapsf_base_url,
            self.enterprise_configuration.key,
            self.enterprise_configuration.secret,
            self.enterprise_configuration.sapsf_company_id,
            sap_user_id,
            SAPSuccessFactorsEnterpriseCustomerConfiguration.USER_TYPE_USER
        )

        response = requests.post(
            url,
            data=payload,
            headers={
                'Authorization': 'Bearer {}'.format(oauth_access_token),
                'content-type': CONTENT_TYPE_APP_JSON
            }
        )

        if response.status_code >= 400:
            raise ClientError(
                'SAPSuccessFactorsAPIClient request failed with status {status_code}: {message}'.format(
                    status_code=response.status_code,
                    message=response.text
                )
            )
        return response.status_code, response.text

    def _call_post_with_session(self, url, payload):
        """
        Make a post request using the session object to a SuccessFactors endpoint.

        Args:
            url (str): The url to post to.
            payload (str): The json encoded payload to post.
        """
        self._create_session()
        response = self.session.post(url, data=payload)
        if response.status_code >= 400:
            LOGGER.error(generate_formatted_log(
                'SAPSF',
                self.enterprise_configuration.enterprise_customer.uuid,
                None,
                None,
                f'Error status_code {response.status_code} and response: {response.text}'
                f' while posting to URL {url} with payload {payload}'
            ))
        return response.status_code, response.text

    def get_inactive_sap_learners(self):
        """
        Make a GET request using the session object to a SuccessFactors endpoint for inactive learners.

        Example:
            sap_search_student_url: "/learning/odatav4/searchStudent/v1/Students?
                $filter=criteria/isActive eq False&$select=studentID"

            SAP API response: {
                u'@odata.metadataEtag': u'W/"17090d86-20fa-49c8-8de0-de1d308c8b55"',
                u'value': [
                    {
                        u'studentID': u'admint6',
                    },
                    {
                        u'studentID': u'adminsap1',
                    }
                ]
            }

        Returns: List of inactive learners
        [
            {
                u'studentID': u'admint6'
            },
            {
                u'studentID': u'adminsap1'
            }
        ]
        """
        self._create_session()
        sap_search_student_url = '{sapsf_base_url}/{search_students_path}?$filter={search_filter}'.format(
            sapsf_base_url=self.enterprise_configuration.sapsf_base_url.rstrip('/'),
            search_students_path=self.global_sap_config.search_student_api_path.rstrip('/'),
            search_filter='criteria/isActive eq False&$select=studentID',
        )
        all_inactive_learners = self._call_search_students_recursively(
            sap_search_student_url,
            all_inactive_learners=[],
            page_size=500,
            start_at=0
        )
        return all_inactive_learners

    def _call_search_students_recursively(self, sap_search_student_url, all_inactive_learners, page_size, start_at):
        """
        Make recursive GET calls to traverse the paginated API response for search students.
        """
        search_student_paginated_url = '{sap_search_student_url}&{pagination_criterion}'.format(
            sap_search_student_url=sap_search_student_url,
            pagination_criterion='$count=true&$top={page_size}&$skip={start_at}'.format(
                page_size=page_size,
                start_at=start_at,
            ),
        )
        try:
            response = self.session.get(search_student_paginated_url)
            sap_inactive_learners = response.json()
        except ValueError as error:
            raise ClientError(response, response.status_code) from error
        except (ConnectionError, Timeout) as exc:
            LOGGER.error(exc)
            LOGGER.error(
                'Unable to fetch inactive learners from SAP searchStudent API with url '
                '"{%s}".', search_student_paginated_url,
            )
            return None

        if 'error' in sap_inactive_learners:
            try:
                LOGGER.error(
                    'SAP searchStudent API for customer %s and base url %s returned response with '
                    'error message "%s" and with error code "%s".',
                    self.enterprise_configuration.enterprise_customer.name,
                    self.enterprise_configuration.sapsf_base_url,
                    sap_inactive_learners['error'].get('message'),
                    sap_inactive_learners['error'].get('code'),
                )
            except AttributeError:
                LOGGER.error(
                    'SAP searchStudent API for customer %s and base url %s returned response with '
                    'error message "%s" and with error code "%s".',
                    self.enterprise_configuration.enterprise_customer.name,
                    self.enterprise_configuration.sapsf_base_url,
                    sap_inactive_learners['error'],
                    response.status_code,
                )
            return None

        new_page_start_at = page_size + start_at
        total_inactive_learners = sap_inactive_learners['@odata.count']
        inactive_learners_on_page = sap_inactive_learners['value']
        LOGGER.info(
            'SAP SF searchStudent API returned [%d] inactive learners of total [%d] starting from [%d] for '
            'enterprise customer [%s]',
            len(inactive_learners_on_page), total_inactive_learners, start_at,
            self.enterprise_configuration.enterprise_customer.name
        )

        all_inactive_learners += inactive_learners_on_page
        if total_inactive_learners > new_page_start_at:
            return self._call_search_students_recursively(
                sap_search_student_url,
                all_inactive_learners,
                page_size=page_size,
                start_at=new_page_start_at,
            )

        return all_inactive_learners
