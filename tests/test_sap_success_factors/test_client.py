# -*- coding: utf-8 -*-
"""
Tests for clients in integrated_channels.
"""
from __future__ import absolute_import, unicode_literals, with_statement

import datetime
import json
import time
import unittest

import requests
import responses
from flaky import flaky
from integrated_channels.sap_success_factors.client import SAPSuccessFactorsAPIClient
from integrated_channels.sap_success_factors.models import (
    SAPSuccessFactorsEnterpriseCustomerConfiguration,
    SAPSuccessFactorsGlobalConfiguration,
)
from pytest import mark, raises


class TestSAPSuccessFactorsAPIClient(unittest.TestCase):
    """
    Test SAPSuccessFactors API methods.
    """

    @mark.django_db
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

    @flaky(max_runs=3)
    @mark.django_db
    @responses.activate  # pylint: disable=no-member
    def test_get_oauth_access_token(self):
        expected_response = (self.access_token, datetime.datetime.utcfromtimestamp(self.expires_in + int(time.time())))

        responses.add(  # pylint: disable=no-member
            responses.POST,  # pylint: disable=no-member
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
        assert len(responses.calls) == 1  # pylint: disable=no-member
        assert responses.calls[0].request.url == self.url_base + self.oauth_api_path  # pylint: disable=no-member

    @mark.django_db
    @responses.activate  # pylint: disable=no-member
    def test_get_oauth_access_token_response_missing_fields(self):
        with raises(requests.RequestException):
            responses.add(  # pylint: disable=no-member
                responses.POST,  # pylint: disable=no-member
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

    @mark.django_db
    def test_init_no_config(self):
        with raises(ValueError):
            SAPSuccessFactorsAPIClient(None)

    @mark.django_db
    @responses.activate  # pylint: disable=no-member
    def test_send_completion_status(self):
        responses.add(  # pylint: disable=no-member
            responses.POST,  # pylint: disable=no-member
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

        responses.add(  # pylint: disable=no-member
            responses.POST,  # pylint: disable=no-member
            self.url_base + self.completion_status_api_path,
            json=expected_response_body,
            status=200
        )

        responses.add(  # pylint: disable=no-member
            responses.POST,  # pylint: disable=no-member
            self.url_base + self.oauth_api_path,
            json=self.expected_token_response_body,
            status=200
        )

        expected_response = 200, json.dumps(expected_response_body)

        sap_client = SAPSuccessFactorsAPIClient(self.enterprise_config)
        actual_response = sap_client.send_completion_status(self.user_type, json.dumps(payload))
        assert actual_response == expected_response
        assert len(responses.calls) == 3  # pylint: disable=no-member
        assert responses.calls[0].request.url == self.url_base + self.oauth_api_path  # pylint: disable=no-member
        assert responses.calls[1].request.url == self.url_base + self.oauth_api_path  # pylint: disable=no-member
        expected_url = self.url_base + self.completion_status_api_path
        assert responses.calls[2].request.url == expected_url  # pylint: disable=no-member

    @mark.django_db
    @responses.activate  # pylint: disable=no-member
    def test_send_course_import(self):
        responses.add(  # pylint: disable=no-member
            responses.POST,  # pylint: disable=no-member
            self.url_base + self.oauth_api_path,
            json=self.expected_token_response_body,
            status=200
        )

        payload = {
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
        expected_course_response_body = payload
        expected_course_response_body["@odata.context"] = "$metadata#OcnCourses/$entity"

        responses.add(  # pylint: disable=no-member
            responses.POST,  # pylint: disable=no-member
            self.url_base + self.course_api_path,
            json=expected_course_response_body,
            status=200
        )

        expected_response = 200, json.dumps(expected_course_response_body)

        sap_client = SAPSuccessFactorsAPIClient(self.enterprise_config)
        actual_response = sap_client.send_course_import(payload)
        assert actual_response == expected_response
        assert len(responses.calls) == 2  # pylint: disable=no-member
        assert responses.calls[0].request.url == self.url_base + self.oauth_api_path  # pylint: disable=no-member
        assert responses.calls[1].request.url == self.url_base + self.course_api_path  # pylint: disable=no-member

    @mark.django_db
    @responses.activate  # pylint: disable=no-member
    def test_expired_access_token(self):
        expired_token_response_body = {"expires_in": 0, "access_token": self.access_token}
        responses.add(  # pylint: disable=no-member
            responses.POST,  # pylint: disable=no-member
            self.url_base + self.oauth_api_path,
            json=expired_token_response_body,
            status=200
        )

        responses.add(  # pylint: disable=no-member
            responses.POST,  # pylint: disable=no-member
            self.url_base + self.oauth_api_path,
            json=self.expected_token_response_body,
            status=200
        )

        payload = {
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
        expected_course_response_body = payload
        expected_course_response_body["@odata.context"] = "$metadata#OcnCourses/$entity"

        responses.add(  # pylint: disable=no-member
            responses.POST,  # pylint: disable=no-member
            self.url_base + self.course_api_path,
            json=expected_course_response_body,
            status=200
        )

        expected_response = 200, json.dumps(expected_course_response_body)

        sap_client = SAPSuccessFactorsAPIClient(self.enterprise_config)
        actual_response = sap_client.send_course_import(payload)
        assert actual_response == expected_response
        assert len(responses.calls) == 3  # pylint: disable=no-member
        assert responses.calls[0].request.url == self.url_base + self.oauth_api_path  # pylint: disable=no-member
        assert responses.calls[1].request.url == self.url_base + self.oauth_api_path  # pylint: disable=no-member
        assert responses.calls[2].request.url == self.url_base + self.course_api_path  # pylint: disable=no-member
