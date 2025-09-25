"""
Tests for the SAPSF API Client.
"""

import datetime
import json
import unittest
from unittest.mock import MagicMock
from urllib.parse import urljoin

import ddt
import pytest
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
from test_utils.factories import EnterpriseCustomerFactory

NOW = datetime.datetime(2017, 1, 2, 3, 4, 5)


@ddt.ddt
@mark.django_db
class TestSAPSuccessFactorsAPIClient(unittest.TestCase):
    """
    Test SAPSuccessFactors API methods.
    """

    def setUp(self):
        super().setUp()
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
            encrypted_key=self.client_id,
            sapsf_base_url=self.url_base,
            sapsf_company_id=self.company_id,
            sapsf_user_id=self.user_id,
            encrypted_secret=self.client_secret
        )
        self.enterprise_config.enterprise_customer = EnterpriseCustomerFactory()
        self.completion_payload = {
            "userID": "abc123",
            "courseID": "course-v1:ColumbiaX+DS101X+1T2016",
            "providerID": "EDX",
            "courseCompleted": "true",
            "completedTimestamp": 1485283526,
            "instructorName": "Professor Professorson",
            "grade": "Pass"
        }

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

        actual_response = SAPSuccessFactorsAPIClient(self.enterprise_config).get_oauth_access_token(
            self.client_id,
            self.client_secret,
            self.company_id,
            self.user_id,
            self.user_type,
            self.enterprise_config.enterprise_customer.uuid
        )
        assert actual_response == expected_response
        assert len(responses.calls) == 1
        assert responses.calls[0].request.url == self.url_base + self.oauth_api_path

    @responses.activate
    def test_get_oauth_access_token_response_missing_fields(self):
        with raises(ClientError):
            responses.add(
                responses.POST,
                self.url_base + self.oauth_api_path,
                json={"issuedFor": "learning_public_api"}
            )

            SAPSuccessFactorsAPIClient(self.enterprise_config).get_oauth_access_token(
                self.client_id,
                self.client_secret,
                self.company_id,
                self.user_id,
                self.user_type,
                self.enterprise_config.enterprise_customer.uuid
            )

    @responses.activate
    def test_get_oauth_access_token_response_non_json(self):
        """ Test  get_oauth_access_token with non json type response"""
        with raises(ClientError):
            responses.add(
                responses.POST,
                urljoin(self.url_base, self.oauth_api_path),
            )
            SAPSuccessFactorsAPIClient(self.enterprise_config).get_oauth_access_token(
                self.client_id,
                self.client_secret,
                self.company_id,
                self.user_id,
                self.user_type,
                self.enterprise_config.enterprise_customer.uuid
            )

    @responses.activate
    def test_send_completion_status(self):
        responses.add(
            responses.POST,
            self.url_base + self.oauth_api_path,
            json=self.expected_token_response_body,
            status=200
        )

        expected_response_body = {"success": "true", "completion_status": self.completion_payload}

        responses.add(
            responses.POST,
            self.url_base + self.completion_status_api_path,
            json=expected_response_body,
            status=200
        )

        expected_response = 200, json.dumps(expected_response_body)

        sap_client = SAPSuccessFactorsAPIClient(self.enterprise_config)
        sap_client._call_post_with_user_override = MagicMock(side_effect=sap_client._call_post_with_user_override)  # pylint: disable=protected-access
        actual_response = sap_client.create_course_completion(self.user_type, json.dumps(self.completion_payload))

        assert actual_response == expected_response
        assert len(responses.calls) == 2
        assert responses.calls[0].request.url == self.url_base + self.oauth_api_path
        expected_url = self.url_base + self.completion_status_api_path
        assert responses.calls[1].request.url == expected_url
        sap_client._call_post_with_user_override.assert_called()  # pylint: disable=protected-access

    @responses.activate
    def test_failed_completion_reporting_exception_handling(self):
        responses.add(
            responses.POST,
            self.url_base + self.oauth_api_path,
            json=self.expected_token_response_body,
            status=200
        )

        expected_error_json = {'Error': 'An error has occurred.'}
        expected_error_message = 'SAPSuccessFactorsAPIClient request failed with status 500: {}'.format(
            json.dumps(expected_error_json)
        )
        expected_error_status_code = 500
        responses.add(
            responses.POST,
            self.url_base + self.completion_status_api_path,
            json=expected_error_json,
            status=expected_error_status_code
        )

        sap_client = SAPSuccessFactorsAPIClient(self.enterprise_config)

        with pytest.raises(ClientError) as client_error:
            sap_client.create_course_completion(self.user_type, json.dumps(self.completion_payload))
        assert client_error.value.message == expected_error_message
        assert client_error.value.status_code == expected_error_status_code

        assert len(responses.calls) == 2

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
        ``create_content_metadata`` should NOT raise ClientError when API request fails with a connection error.
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

        with raises(requests.exceptions.RequestException):
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

        sap_client = SAPSuccessFactorsAPIClient(self.enterprise_config)
        status, _ = sap_client.create_content_metadata(self.content_payload)
        assert status >= 400

    @responses.activate
    def test_expired_access_token(self):
        """
           If our token expires after some call, make sure to get it again.

           Make a call, have the token expire after waiting some time (technically no time since time is frozen),
           and make a call again and notice 2 OAuth calls in total are required.
        """
        expired_token_response_body = {"expires_in": 0, "access_token": self.access_token}
        responses.add(
            responses.POST,
            self.url_base + self.oauth_api_path,
            json=expired_token_response_body,
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
        sap_client.create_content_metadata(self.content_payload)
        assert len(responses.calls) == 4
        assert responses.calls[0].request.url == self.url_base + self.oauth_api_path
        assert responses.calls[1].request.url == self.url_base + self.course_api_path
        assert responses.calls[2].request.url == self.url_base + self.oauth_api_path
        assert responses.calls[3].request.url == self.url_base + self.course_api_path

    @responses.activate
    def test_client_uses_prevent_learner_submit_flag(self):
        responses.add(
            responses.POST,
            self.url_base + self.oauth_api_path,
            json=self.expected_token_response_body,
            status=200
        )

        sap_client = SAPSuccessFactorsAPIClient(self.enterprise_config)
        sap_client.enterprise_configuration.prevent_self_submit_grades = True

        expected_response_body = {"success": "true", "completion_status": self.completion_payload}
        expected_completion_url = self.url_base + sap_client.GENERIC_COURSE_COMPLETION_PATH

        responses.add(
            responses.POST,
            expected_completion_url,
            json=expected_response_body,
            status=200
        )

        expected_response = 200, json.dumps(expected_response_body)
        # Mimic the transformation behaviour in the client since we expect that to occur when the post is called
        expected_payload = self.completion_payload.copy()
        expected_payload['courseCompleted'] = True
        expected_payload = json.dumps(expected_payload)

        payload = json.dumps(self.completion_payload)

        sap_client._call_post_with_session = MagicMock(side_effect=sap_client._call_post_with_session)  # pylint: disable=protected-access
        actual_response = sap_client.create_course_completion(self.user_type, payload)
        assert actual_response == expected_response

        sap_client._call_post_with_session.assert_called_with(expected_completion_url, expected_payload)  # pylint: disable=protected-access

    @responses.activate
    def test_sync_content_metadata_success(self):
        """
        Test that the sync content metadata method works as expected
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
            json=expected_course_response_body,
            status=200
        )

        sap_client = SAPSuccessFactorsAPIClient(self.enterprise_config)
        status, body = sap_client._sync_content_metadata(self.content_payload)  # pylint: disable=protected-access
        assert status == 200
        assert json.loads(body) == expected_course_response_body
        assert len(responses.calls) == 2

    @responses.activate
    def test_sync_content_metadata_too_many_requests(self):
        """
        Test that the sync content metadata method retries when it gets a 429 response.
        """
        responses.add(
            responses.POST,
            self.url_base + self.oauth_api_path,
            json=self.expected_token_response_body,
            status=200
        )

        responses.add(
            responses.POST,
            self.url_base + self.course_api_path,
            status=429
        )

        sap_client = SAPSuccessFactorsAPIClient(self.enterprise_config)
        with freeze_time(NOW):
            status, body = sap_client._sync_content_metadata(self.content_payload)  # pylint: disable=protected-access,unused-variable
        assert status == 429
        assert len(responses.calls) == sap_client.MAX_RETRIES + 1 + 1  # 1 for the auth call

    @responses.activate
    def test_sync_content_metadata_bad_request(self):
        """
        Test that the sync content metadata method returns the response body when it gets a 400 response.
        """
        responses.add(
            responses.POST,
            self.url_base + self.oauth_api_path,
            json=self.expected_token_response_body,
            status=200
        )

        responses.add(
            responses.POST,
            self.url_base + self.course_api_path,
            json={"message": "error"},
            status=400
        )

        sap_client = SAPSuccessFactorsAPIClient(self.enterprise_config)
        status, body = sap_client._sync_content_metadata(self.content_payload)  # pylint: disable=protected-access
        assert status == 400
        assert json.loads(body) == {'message': 'error'}
        assert len(responses.calls) == 2

    @responses.activate
    def test_sync_content_metadata_retry_logic(self):
        """
        Test that the sync content metadata method retries when it gets a 429 response and then succeeds.
        """
        responses.add(
            responses.POST,
            self.url_base + self.oauth_api_path,
            json=self.expected_token_response_body,
            status=200
        )

        responses.add(
            responses.POST,
            self.url_base + self.course_api_path,
            status=429
        )

        responses.add(
            responses.POST,
            self.url_base + self.course_api_path,
            json=self.content_payload,
            status=200
        )

        sap_client = SAPSuccessFactorsAPIClient(self.enterprise_config)
        with freeze_time(NOW):
            status, body = sap_client._sync_content_metadata(self.content_payload)  # pylint: disable=protected-access
        assert status == 200
        assert json.loads(body) == self.content_payload
        assert len(responses.calls) == 3

    @unittest.mock.patch('integrated_channels.sap_success_factors.client.LOGGER')
    def test_get_oauth_access_token_exception_logging(self, mock_logger):
        """Test that get_oauth_access_token logs exceptions correctly."""
        sap_client = SAPSuccessFactorsAPIClient(self.enterprise_config)

        # Mock a response that will cause a ValueError
        mock_response = unittest.mock.Mock()
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.status_code = 500

        with unittest.mock.patch('requests.post', return_value=mock_response):
            with pytest.raises(ClientError):
                sap_client.get_oauth_access_token(
                    self.client_id,
                    self.client_secret,
                    self.company_id,
                    self.user_id,
                    self.user_type,
                    self.enterprise_config.enterprise_customer.uuid,
                )

        # Verify the logging call was made with correct parameters
        mock_logger.exception.assert_called_once()
        args, kwargs = mock_logger.exception.call_args
        self.assertIn('SAP SF OAuth2 POST response is of invalid format', args[0])
        self.assertEqual(kwargs['extra']['channel_name'], 'SAP')
        self.assertEqual(kwargs['extra']['enterprise_customer_uuid'], self.enterprise_config.enterprise_customer.uuid)
        self.assertEqual(kwargs['extra']['status_code'], 500)

    @unittest.mock.patch('integrated_channels.sap_success_factors.client.LOGGER')
    def test_call_search_students_recursively_exception_logging(self, mock_logger):
        """Test that _call_search_students_recursively logs exceptions correctly."""
        sap_client = SAPSuccessFactorsAPIClient(self.enterprise_config)
        sap_client.session = unittest.mock.Mock()

        # Mock a response that will cause a ValueError
        mock_response = unittest.mock.Mock()
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.status_code = 500
        sap_client.session.get.return_value = mock_response

        with pytest.raises(ClientError):
            sap_client._call_search_students_recursively(  # pylint: disable=protected-access
                "http://test.com/students",
                [],
                500,
                0
            )

        # Verify the logging was not called for ValueError exception (it should re-raise as ClientError)
        mock_logger.error.assert_not_called()

    @unittest.mock.patch('integrated_channels.sap_success_factors.client.LOGGER')
    def test_call_search_students_recursively_error_response_logging(self, mock_logger):
        """Test that _call_search_students_recursively logs error responses correctly."""
        sap_client = SAPSuccessFactorsAPIClient(self.enterprise_config)
        sap_client.session = unittest.mock.Mock()
        sap_client.IntegratedChannelAPIRequestLogs = unittest.mock.Mock()
        sap_client.IntegratedChannelAPIRequestLogs.store_api_call = unittest.mock.Mock()

        # Mock a response with an error
        mock_response = unittest.mock.Mock()
        mock_response.json.return_value = {'error': {'message': 'Test error message', 'code': 'TEST_ERROR'}}
        mock_response.status_code = 400
        sap_client.session.get.return_value = mock_response

        result = sap_client._call_search_students_recursively(  # pylint: disable=protected-access
            "http://test.com/students",
            [],
            500,
            0
        )

        # Should return None due to error
        self.assertIsNone(result)

        # Verify the logging call was made with correct parameters
        mock_logger.error.assert_called()
        args, kwargs = mock_logger.error.call_args
        self.assertIn('SAP searchStudent API', args[0])
        self.assertIn('Test error message', args[0])
        self.assertEqual(kwargs['extra']['channel_name'], self.enterprise_config.channel_code())
        self.assertEqual(kwargs['extra']['enterprise_customer_uuid'], self.enterprise_config.enterprise_customer.uuid)
        self.assertEqual(kwargs['extra']['plugin_configuration_id'], self.enterprise_config.id)
        self.assertEqual(kwargs['extra']['status_code'], 'TEST_ERROR')
