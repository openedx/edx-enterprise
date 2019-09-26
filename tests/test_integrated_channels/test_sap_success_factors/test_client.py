# -*- coding: utf-8 -*-
"""
Tests for the SAPSF API Client.
"""

from __future__ import absolute_import, unicode_literals, with_statement

import datetime
import json
import unittest

import ddt
import requests
import responses
from freezegun import freeze_time
from pytest import mark, raises

from integrated_channels.exceptions import ClientError
from integrated_channels.sap_success_factors.client import SAPSuccessFactorsAPIClient
from integrated_channels.sap_success_factors.models import (
    SAPSuccessFactorsEnterpriseCustomerConfiguration,
    SAPSuccessFactorsGlobalConfiguration,
)

NOW = datetime.datetime(2017, 1, 2, 3, 4, 5)


@ddt.ddt
@mark.django_db
class TestSAPSuccessFactorsAPIClient(unittest.TestCase):
    """
    Test SAPSuccessFactors API methods.
    """

    def setUp(self):
        super(TestSAPSuccessFactorsAPIClient, self).setUp()
        self.oauth_api_path = "learning/oauth-api/rest/v1/token"
        self.completion_status_api_path = "learning/odatav4/public/admin/ocn/v1/current-user/item/learning-event"
        self.course_api_path = "learning/odatav4/public/admin/ocn/v1/OcnCourses"
        self.url_base = "http://test.successfactors.com/"
        self.client_id = "client_id"
        self.client_secret = "client_secret"
        self.company_id = "company_id"
        self.user_id = "user_id"
        self.user_type = "user"
        self.expires_in = 1800
        self.access_token = "access_token"
        self.content_payload = {
            "ocnCourses": [
                {
                    "courseID": "TED1",
                    "providerID": "TED",
                    "status": "ACTIVE",
                    "title": [
                        {
                            "locale": "English",
                            "value": "Can a computer write poetry?"
                        }
                    ]
                }
            ]
        }

        SAPSuccessFactorsGlobalConfiguration.objects.create(
            completion_status_api_path=self.completion_status_api_path,
            course_api_path=self.course_api_path,
            oauth_api_path=self.oauth_api_path
        )

        self.expected_token_response_body = {"expires_in": self.expires_in, "access_token": self.access_token}
        self.enterprise_config = SAPSuccessFactorsEnterpriseCustomerConfiguration(
            key=self.client_id,
            sapsf_base_url=self.url_base,
            sapsf_company_id=self.company_id,
            sapsf_user_id=self.user_id,
            secret=self.client_secret
        )

    @responses.activate
    @freeze_time(NOW)
    def test_get_oauth_access_token(self):
        expected_response = (self.access_token, NOW + datetime.timedelta(seconds=self.expires_in))

        responses.add(
            responses.POST,
            self.url_base + self.oauth_api_path,
            json=self.expected_token_response_body,
            status=200
        )

        actual_response = SAPSuccessFactorsAPIClient.get_oauth_access_token(
            self.url_base,
            self.client_id,
            self.client_secret,
            self.company_id,
            self.user_id,
            self.user_type
        )
        assert actual_response == expected_response
        assert len(responses.calls) == 1
        assert responses.calls[0].request.url == self.url_base + self.oauth_api_path

    @responses.activate
    def test_get_oauth_access_token_response_missing_fields(self):
        with raises(requests.RequestException):
            responses.add(
                responses.POST,
                self.url_base + self.oauth_api_path,
                json={"issuedFor": "learning_public_api"}
            )

            SAPSuccessFactorsAPIClient.get_oauth_access_token(
                self.url_base,
                self.client_id,
                self.client_secret,
                self.company_id,
                self.user_id,
                self.user_type
            )

    @responses.activate
    def test_send_completion_status(self):
        responses.add(
            responses.POST,
            self.url_base + self.oauth_api_path,
            json=self.expected_token_response_body,
            status=200
        )

        payload = {
            "userID": "abc123",
            "courseID": "course-v1:ColumbiaX+DS101X+1T2016",
            "providerID": "EDX",
            "courseCompleted": "true",
            "completedTimestamp": 1485283526,
            "instructorName": "Professor Professorson",
            "grade": "Pass"
        }
        expected_response_body = {"success": "true", "completion_status": payload}

        responses.add(
            responses.POST,
            self.url_base + self.completion_status_api_path,
            json=expected_response_body,
            status=200
        )

        responses.add(
            responses.POST,
            self.url_base + self.oauth_api_path,
            json=self.expected_token_response_body,
            status=200
        )

        expected_response = 200, json.dumps(expected_response_body)

        sap_client = SAPSuccessFactorsAPIClient(self.enterprise_config)
        actual_response = sap_client.create_course_completion(self.user_type, json.dumps(payload))
        assert actual_response == expected_response
        assert len(responses.calls) == 3
        assert responses.calls[0].request.url == self.url_base + self.oauth_api_path
        assert responses.calls[1].request.url == self.url_base + self.oauth_api_path
        expected_url = self.url_base + self.completion_status_api_path
        assert responses.calls[2].request.url == expected_url

    @responses.activate
    @ddt.data('create_content_metadata', 'update_content_metadata', 'delete_content_metadata')
    def test_content_import(self, client_method):
        responses.add(
            responses.POST,
            self.url_base + self.oauth_api_path,
            json=self.expected_token_response_body,
            status=200
        )

        expected_course_response_body = self.content_payload
        expected_course_response_body["@odata.context"] = "$metadata#OcnCourses/$entity"

        responses.add(
            responses.POST,
            self.url_base + self.course_api_path,
            json=expected_course_response_body,
            status=200
        )

        sap_client = SAPSuccessFactorsAPIClient(self.enterprise_config)
        getattr(sap_client, client_method)(self.content_payload)
        assert len(responses.calls) == 2
        assert responses.calls[0].request.url == self.url_base + self.oauth_api_path
        assert responses.calls[1].request.url == self.url_base + self.course_api_path

    @responses.activate
    def test_sap_api_connection_error(self):
        """
        ``create_content_metadata`` should raise ClientError when API request fails with a connection error.
        """
        responses.add(
            responses.POST,
            self.url_base + self.oauth_api_path,
            json=self.expected_token_response_body,
            status=200
        )

        expected_course_response_body = self.content_payload
        expected_course_response_body["@odata.context"] = "$metadata#OcnCourses/$entity"

        responses.add(
            responses.POST,
            self.url_base + self.course_api_path,
            body=requests.exceptions.RequestException()
        )

        with raises(ClientError):
            sap_client = SAPSuccessFactorsAPIClient(self.enterprise_config)
            sap_client.create_content_metadata(self.content_payload)

    @responses.activate
    def test_sap_api_application_error(self):
        """
        ``create_content_metadata`` should raise ClientError when API request fails with an application error.
        """
        responses.add(
            responses.POST,
            self.url_base + self.oauth_api_path,
            json=self.expected_token_response_body,
            status=200
        )

        expected_course_response_body = self.content_payload
        expected_course_response_body["@odata.context"] = "$metadata#OcnCourses/$entity"

        responses.add(
            responses.POST,
            self.url_base + self.course_api_path,
            json={'message': 'error'},
            status=400
        )

        with raises(ClientError):
            sap_client = SAPSuccessFactorsAPIClient(self.enterprise_config)
            sap_client.create_content_metadata(self.content_payload)

    @responses.activate
    def test_expired_access_token(self):
        expired_token_response_body = {"expires_in": 0, "access_token": self.access_token}
        responses.add(
            responses.POST,
            self.url_base + self.oauth_api_path,
            json=expired_token_response_body,
            status=200
        )

        responses.add(
            responses.POST,
            self.url_base + self.oauth_api_path,
            json=self.expected_token_response_body,
            status=200
        )

        expected_course_response_body = self.content_payload
        expected_course_response_body["@odata.context"] = "$metadata#OcnCourses/$entity"

        responses.add(
            responses.POST,
            self.url_base + self.course_api_path,
            json=expected_course_response_body,
            status=200
        )

        sap_client = SAPSuccessFactorsAPIClient(self.enterprise_config)
        sap_client.create_content_metadata(self.content_payload)
        assert len(responses.calls) == 3
        assert responses.calls[0].request.url == self.url_base + self.oauth_api_path
        assert responses.calls[1].request.url == self.url_base + self.oauth_api_path
        assert responses.calls[2].request.url == self.url_base + self.course_api_path
