# -*- coding: utf-8 -*-
"""
Client for connecting to SAP SuccessFactors.
"""
from __future__ import absolute_import, unicode_literals

import datetime
import time

import requests
from integrated_channels.integrated_channel.client import IntegratedChannelApiClient

from django.apps import apps


class SAPSuccessFactorsAPIClient(IntegratedChannelApiClient):  # pylint: disable=abstract-method
    """
    Client for connecting to SAP SuccessFactors.

    Specifically, this class supports obtaining access tokens and posting to the courses and
     completion status endpoints.
    """

    SESSION_TIMEOUT = 5

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
            RequestException: If an unexpected response format was received that we could not parse.
        """
        SAPSuccessFactorsGlobalConfiguration = apps.get_model(  # pylint: disable=invalid-name
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
            headers={'content-type': 'application/json'}
        )

        response.raise_for_status()
        data = response.json()
        try:
            return data['access_token'], datetime.datetime.utcfromtimestamp(data['expires_in'] + int(time.time()))
        except KeyError:
            raise requests.RequestException(response=response)

    def __init__(self, enterprise_configuration):
        """
        Instantiate a new client.

        Args:
            enterprise_configuration (SAPSuccessFactorsEnterpriseCustomerConfiguration): An enterprise customers's
            configuration model for connecting with SAP SuccessFactors
        """
        super(SAPSuccessFactorsAPIClient, self).__init__(enterprise_configuration)
        self.global_sap_config = apps.get_model('sap_success_factors', 'SAPSuccessFactorsGlobalConfiguration').current()
        self._create_session()

    def _create_session(self):
        """
        Instantiate a new session object for use in connecting with SAP SuccessFactors
        """
        session = requests.Session()
        session.timeout = self.SESSION_TIMEOUT

        oauth_access_token, expires_at = SAPSuccessFactorsAPIClient.get_oauth_access_token(
            self.enterprise_configuration.sapsf_base_url,
            self.enterprise_configuration.key,
            self.enterprise_configuration.secret,
            self.enterprise_configuration.sapsf_company_id,
            self.enterprise_configuration.sapsf_user_id,
            self.enterprise_configuration.user_type
        )

        session.headers['Authorization'] = 'Bearer {}'.format(oauth_access_token)
        session.headers['content-type'] = 'application/json'
        self.session = session
        self.expires_at = expires_at

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
        url = self.enterprise_configuration.sapsf_base_url + self.global_sap_config.completion_status_api_path
        return self._call_post_with_user_override(user_id, url, payload)

    def create_course_content(self, payload):
        """
        Send courses payload to the SuccessFactors OCN Course Import endpoint

        Args:
            payload: JSON encoded object containing course import data per SuccessFactors documentation.

        Returns:
            The body of the response from SAP SuccessFactors, if successful
        Raises:
            HTTPError: if we received a failure response code from SAP SuccessFactors
        """
        url = self.enterprise_configuration.sapsf_base_url + self.global_sap_config.course_api_path
        return self._call_post_with_session(url, payload)

    def _call_post_with_user_override(self, sap_user_id, url, payload):
        """
        Make a post request with an auth token acquired for a specific user to a SuccessFactors endpoint.

        Args:
            sap_user_id (str): The user to use to retrieve an auth token.
            url (str): The url to post to.
            payload (str): The json encoded payload to post.
        """
        SAPSuccessFactorsEnterpriseCustomerConfiguration = apps.get_model(  # pylint: disable=invalid-name
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
                'content-type': 'application/json'
            }
        )

        return response.status_code, response.text

    def _call_post_with_session(self, url, payload):
        """
        Make a post request using the session object to a SuccessFactors endpoint.

        Args:
            url (str): The url to post to.
            payload (str): The json encoded payload to post.
        """
        now = datetime.datetime.utcnow()
        if now >= self.expires_at:
            # Create a new session with a valid token
            self.session.close()
            self._create_session()
        response = self.session.post(url, data=payload)
        return response.status_code, response.text
