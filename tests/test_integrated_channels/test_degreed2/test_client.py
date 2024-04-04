# -*- coding: utf-8 -*-
"""
Tests for Degreed2 client for integrated_channels.
"""

import datetime
import json
import unittest

import mock
import pytest
import requests
import responses
from freezegun import freeze_time
from six.moves.urllib.parse import urljoin

from django.apps.registry import apps

from enterprise.api_client.enterprise_catalog import EnterpriseCatalogApiClient
from enterprise.models import EnterpriseCustomerUser
from integrated_channels.degreed2.client import Degreed2APIClient
from integrated_channels.exceptions import ClientError
from test_utils import factories

NOW = datetime.datetime(2017, 1, 2, 3, 4, 5, tzinfo=datetime.timezone.utc)
NOW_TIMESTAMP_FORMATTED = NOW.strftime('%F')

app_config = apps.get_app_config("degreed2")


def create_course_payload():
    return json.dumps(
        {
            'courses': [{
                'title': 'title',
                'summary': 'description',
                'image-url': 'image',
                'url': 'enrollment_url',
                'language': 'content_language',
                'external-id': 'key',
                'duration': 'duration',
                'duration-type': 'Days',
            }],
        }, sort_keys=True
    ).encode('utf-8')


@pytest.mark.django_db
@freeze_time(NOW)
class TestDegreed2ApiClient(unittest.TestCase):
    """
    Test Degreed2 API client methods.
    """

    def setUp(self):
        super().setUp()
        self.url_base = "http://betatest.degreed.com/"
        self.oauth_api_path = "oauth/token"
        self.oauth_url = urljoin(self.url_base, self.oauth_api_path)
        self.completion_status_api_path = "api/v1/provider/completion/course"
        self.completion_status_url = urljoin(self.url_base, self.completion_status_api_path)
        self.course_api_path = "api/v1/provider/content/course"
        self.course_url = urljoin(self.url_base, self.course_api_path)
        # self.client_id = "client_id"
        # self.client_secret = "client_secret"
        # self.company_id = "company_id"
        # self.user_id = "user_id"
        # self.user_pass = "user_pass"
        self.expires_in = 1800
        self.access_token = "access_token"
        self.expected_token_response_body = {"expires_in": self.expires_in, "access_token": self.access_token}
        self.enterprise_config = factories.Degreed2EnterpriseCustomerConfigurationFactory()
        self.too_fast_response = {
            "errors": [
                {
                    "id": "c2e2f849-ed0a-4ed8-833c-f9008113948c",
                    "code": "quota-exceeded",
                    "status": 429,
                    "title": "API calls quota exceeded.",
                    "detail": "Maximum 70 requests allowed per 1m."
                }
            ]
        }
        self.user_deleted_response = {
            "errors": [
                {
                    "id": "c2e2f849-ed0a-4ed8-833c-f9008113948c",
                    "code": "bad-request",
                    "status": 400,
                    "title": "Bad Request",
                    "detail": "Invalid user identifier: test-learner@example.com",
                    "source": "test-learner@example.com"
                }
            ]
        }

    def test_calculate_backoff(self):
        """
        Test the default math of the backoff calculator
        """
        client = Degreed2APIClient(self.enterprise_config)
        assert client._calculate_backoff(0) == 1  # pylint: disable=protected-access
        assert client._calculate_backoff(1) == 2  # pylint: disable=protected-access
        assert client._calculate_backoff(2) == 4  # pylint: disable=protected-access
        assert client._calculate_backoff(3) == 8  # pylint: disable=protected-access

    @responses.activate
    def test_oauth_with_non_json_response(self):
        """ Test  _get_oauth_access_token with non json type response"""
        client = Degreed2APIClient(self.enterprise_config)
        with pytest.raises(ClientError):
            responses.add(
                responses.POST,
                client.get_oauth_url(),
            )
            client._get_oauth_access_token(  # pylint: disable=protected-access
                Degreed2APIClient.ALL_DESIRED_SCOPES
            )

    @responses.activate
    def test_create_course_completion(self):
        """
        ``create_course_completion`` should use the appropriate URLs for transmission.
        """
        degreed_api_client = Degreed2APIClient(self.enterprise_config)
        responses.add(
            responses.POST,
            degreed_api_client.get_oauth_url(),
            json=self.expected_token_response_body,
            status=200
        )
        responses.add(
            responses.POST,
            degreed_api_client.get_completions_url(),
            json='{}',
            status=200
        )

        payload = {
            "data": {
                "attributes": {
                    "user-id": 'test-learner@example.com',
                    "user-identifier-type": "Email",
                    "content-id": 'DemoX',
                    "content-id-type": "externalId",
                    "content-type": "course",
                    "completed-at": NOW_TIMESTAMP_FORMATTED,
                    "percentile": 80,
                }
            }
        }
        output = degreed_api_client.create_course_completion('test-learner@example.com', json.dumps(payload))

        assert output == (200, '"{}"')
        assert len(responses.calls) == 2
        assert responses.calls[0].request.url == degreed_api_client.get_oauth_url()
        assert responses.calls[1].request.url == degreed_api_client.get_completions_url()

    @responses.activate
    def test_create_course_completion_for_deleted_user(self):
        """
        ``create_course_completion`` should handle exception for deleted users gracefully
        by unlinking that user from enterprise
        """
        degreed_api_client = Degreed2APIClient(self.enterprise_config)
        responses.add(
            responses.POST,
            degreed_api_client.get_oauth_url(),
            json=self.expected_token_response_body,
            status=200
        )
        responses.add(
            responses.POST,
            degreed_api_client.get_completions_url(),
            json=self.user_deleted_response,
            status=400
        )

        payload = {
            "data": {
                "attributes": {
                    "user-id": 'test-learner@example.com',
                    "user-identifier-type": "Email",
                    "content-id": 'DemoX',
                    "content-id-type": "externalId",
                    "content-type": "course",
                    "completed-at": NOW_TIMESTAMP_FORMATTED,
                    "percentile": 80,
                }
            }
        }
        email = payload.get("data").get("attributes").get("user-id")
        with mock.patch.object(EnterpriseCustomerUser.objects, 'unlink_user') as unlink_user_mock:
            degreed_api_client.create_course_completion(email, json.dumps(payload))
            unlink_user_mock.assert_called_once()
        assert len(responses.calls) == 2
        assert responses.calls[0].request.url == degreed_api_client.get_oauth_url()
        assert responses.calls[1].request.url == degreed_api_client.get_completions_url()

    @responses.activate
    def test_delete_course_completion(self):
        """
        TODO this feature isn't implemented yet.
        """
        enterprise_config = factories.Degreed2EnterpriseCustomerConfigurationFactory()
        degreed_api_client = Degreed2APIClient(enterprise_config)
        degreed_api_client.delete_course_completion(None, None)

    @mock.patch('integrated_channels.degreed2.client.Degreed2APIClient._get')
    def test_fetch_degreed_course_id_cache(self, mock_get_request):
        """
        ``fetch_degreed_course_id`` should fetch data from the API only if the cache is empty.
        """
        enterprise_config = factories.Degreed2EnterpriseCustomerConfigurationFactory()
        degreed_api_client = Degreed2APIClient(enterprise_config)
        mock_get_request.return_value = (
            200, '{"data": [{"id": "degreed_course_id"}]}'
        )
        degreed_external_course_id_1 = 'course_id_1'
        degreed_external_course_id_2 = 'course_id_2'

        degreed_api_client.fetch_degreed_course_id(degreed_external_course_id_1)
        degreed_api_client.fetch_degreed_course_id(degreed_external_course_id_2)
        assert mock_get_request.call_count == 2

        # The second call for the same course id should return the degreed_course_id from the cache
        mock_get_request.reset_mock()
        degreed_api_client.fetch_degreed_course_id(degreed_external_course_id_1)
        degreed_api_client.fetch_degreed_course_id(degreed_external_course_id_2)
        assert mock_get_request.call_count == 0

    @responses.activate
    @pytest.mark.django_db
    @mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
    def test_create_content_metadata_success(self):
        """
        ``create_content_metadata`` should use expected URLs and receive correct response.
        """
        enterprise_config = factories.Degreed2EnterpriseCustomerConfigurationFactory()
        degreed_api_client = Degreed2APIClient(enterprise_config)
        oauth_url = degreed_api_client.get_oauth_url()
        course_url = degreed_api_client.get_courses_url()
        degreed_course_id = 'degreed-id'
        responses.add(
            responses.POST,
            oauth_url,
            json=self.expected_token_response_body,
            status=200
        )
        responses.add(
            responses.POST,
            course_url,
            json='{}',
            status=200
        )
        responses.add(
            responses.GET,
            EnterpriseCatalogApiClient.API_BASE_URL
            + EnterpriseCatalogApiClient.CONTENT_METADATA_IDENTIFIER_ENDPOINT.format(
                enterprise_config.enterprise_customer.uuid, "key/"
            ),
            json={"skill_names": ["Supply Chain", "Supply Chain Management"]},
            status=200,
        )
        # The second call for the same course id should return the degreed_course_id from the cache
        responses.add(
            responses.GET,
            course_url + "?filter%5Bexternal_id%5D=key",
            json={"data": [{"id": degreed_course_id}]},
            status=200,
        )
        responses.add(
            responses.PATCH,
            f'{enterprise_config.degreed_base_url}api/v2/content/{degreed_course_id}/relationships/skills',
            json='{}',
            status=200
        )

        status_code, response_body = degreed_api_client.create_content_metadata(create_course_payload())
        assert len(responses.calls) == 4
        assert responses.calls[0].request.url == oauth_url
        assert responses.calls[1].request.url == course_url
        assert status_code == 200
        assert response_body == '"{}"'

    @responses.activate
    @mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
    def test_create_content_metadata_retry_success(self):
        """
        ``create_content_metadata`` should hit a 429 and retry and receive correct response.
        """
        enterprise_config = factories.Degreed2EnterpriseCustomerConfigurationFactory()
        degreed_api_client = Degreed2APIClient(enterprise_config)
        oauth_url = degreed_api_client.get_oauth_url()
        course_url = degreed_api_client.get_courses_url()
        degreed_course_id = "degreed-id"

        responses.add(
            responses.POST,
            oauth_url,
            json=self.expected_token_response_body,
            status=200,
        )
        responses.add(
            responses.POST,
            course_url,
            json=self.too_fast_response,
            status=429,
        )
        responses.add(
            responses.POST,
            course_url,
            json='{}',
            status=200,
        )
        responses.add(
            responses.GET,
            EnterpriseCatalogApiClient.API_BASE_URL
            + EnterpriseCatalogApiClient.CONTENT_METADATA_IDENTIFIER_ENDPOINT.format(
                enterprise_config.enterprise_customer.uuid, "key/"
            ),
            json={"skill_names": ["Supply Chain", "Supply Chain Management"]},
            status=200,
        )
        # The second call for the same course id should return the degreed_course_id from the cache
        responses.add(
            responses.GET,
            course_url + "?filter%5Bexternal_id%5D=key",
            json={"data": [{"id": degreed_course_id}]},
            status=200,
        )
        responses.add(
            responses.PATCH,
            f"{enterprise_config.degreed_base_url}api/v2/content/{degreed_course_id}/relationships/skills",
            json="{}",
            status=200,
        )
        status_code, response_body = degreed_api_client.create_content_metadata(create_course_payload())
        assert len(responses.calls) == 5
        assert responses.calls[0].request.url == oauth_url
        assert responses.calls[1].request.url == course_url
        assert responses.calls[2].request.url == course_url
        assert status_code == 200
        assert response_body == '"{}"'

    @responses.activate
    def test_create_content_metadata_retry_exhaust(self):
        """
        ``create_content_metadata`` should hit multiple 429's and eventually fail.
        """
        enterprise_config = factories.Degreed2EnterpriseCustomerConfigurationFactory()
        degreed_api_client = Degreed2APIClient(enterprise_config)
        oauth_url = degreed_api_client.get_oauth_url()
        course_url = degreed_api_client.get_courses_url()

        responses.add(
            responses.POST,
            oauth_url,
            json=self.expected_token_response_body,
            status=200,
        )
        responses.add(
            responses.POST,
            course_url,
            json=self.too_fast_response,
            status=429,
        )
        responses.add(
            responses.POST,
            course_url,
            json=self.too_fast_response,
            status=429,
        )
        responses.add(
            responses.POST,
            course_url,
            json=self.too_fast_response,
            status=429,
        )
        responses.add(
            responses.POST,
            course_url,
            json=self.too_fast_response,
            status=429,
        )

        with pytest.raises(ClientError):
            status_code, response_body = degreed_api_client.create_content_metadata(create_course_payload())
            assert len(responses.calls) == 5
            assert responses.calls[0].request.url == oauth_url
            assert responses.calls[1].request.url == course_url
            assert responses.calls[2].request.url == course_url
            assert responses.calls[3].request.url == course_url
            assert responses.calls[4].request.url == course_url
            assert status_code == 429
            assert json.loads(response_body) == self.too_fast_response

    @responses.activate
    @mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
    def test_create_content_metadata_course_exists(self):
        """
        ``create_content_metadata`` should return 409 status and not fail
        """
        enterprise_config = factories.Degreed2EnterpriseCustomerConfigurationFactory()
        degreed_api_client = Degreed2APIClient(enterprise_config)
        oauth_url = degreed_api_client.get_oauth_url()
        course_url = degreed_api_client.get_courses_url()
        degreed_course_id = "degreed-id"

        responses.add(
            responses.POST,
            oauth_url,
            json=self.expected_token_response_body,
            status=200
        )
        responses.add(
            responses.POST,
            course_url,
            json='{}',
            status=409
        )
        responses.add(
            responses.GET,
            EnterpriseCatalogApiClient.API_BASE_URL
            + EnterpriseCatalogApiClient.CONTENT_METADATA_IDENTIFIER_ENDPOINT.format(
                enterprise_config.enterprise_customer.uuid, "key/"
            ),
            json={"skill_names": ["Supply Chain", "Supply Chain Management"]},
            status=200,
        )
        responses.add(
            responses.GET,
            course_url + "?filter%5Bexternal_id%5D=key",
            json={"data": [{"id": degreed_course_id}]},
            status=200,
        )
        responses.add(
            responses.PATCH,
            f'{enterprise_config.degreed_base_url}api/v2/content/{degreed_course_id}/relationships/skills',
            json='{}',
            status=200
        )
        responses.add(
            responses.PATCH,
            f'{enterprise_config.degreed_base_url}api/v2/content/courses/{degreed_course_id}',
            json='{}',
            status=200
        )
        status_code, _ = degreed_api_client.create_content_metadata(create_course_payload())
        # we treat as "course exists" as a success
        assert status_code == 200

    @responses.activate
    @mock.patch('integrated_channels.degreed2.client.Degreed2APIClient.fetch_degreed_course_id')
    @mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
    def test_update_content_metadata_success(self, mock_fetch_degreed_course_id):
        """
        ``update_content_metadata`` should use the appropriate URLs for transmission.
        """
        mock_fetch_degreed_course_id.return_value = 'a_course_id'
        enterprise_config = factories.Degreed2EnterpriseCustomerConfigurationFactory()
        degreed_api_client = Degreed2APIClient(enterprise_config)
        oauth_url = degreed_api_client.get_oauth_url()
        degreed_course_id = "a_course_id"
        course_url = degreed_api_client.get_courses_url()

        responses.add(
            responses.POST,
            oauth_url,
            json=self.expected_token_response_body,
            status=200
        )
        responses.add(
            responses.PATCH,
            f'{degreed_api_client.get_courses_url()}/a_course_id',
            json='{}',
            status=200
        )
        responses.add(
            responses.GET,
            EnterpriseCatalogApiClient.API_BASE_URL
            + EnterpriseCatalogApiClient.CONTENT_METADATA_IDENTIFIER_ENDPOINT.format(
                enterprise_config.enterprise_customer.uuid, "key/"
            ),
            json={"skill_names": ["Supply Chain", "Supply Chain Management"]},
            status=200,
        )
        responses.add(
            responses.GET,
            course_url + "?filter%5Bexternal_id%5D=key",
            json={"data": [{"id": degreed_course_id}]},
            status=200,
        )
        responses.add(
            responses.PATCH,
            f'{enterprise_config.degreed_base_url}api/v2/content/{degreed_course_id}/relationships/skills',
            json='{}',
            status=200
        )
        status_code, response_body = degreed_api_client.update_content_metadata(create_course_payload())
        assert len(responses.calls) == 4
        assert responses.calls[0].request.url == oauth_url
        assert responses.calls[1].request.url == f'{degreed_api_client.get_courses_url()}/a_course_id'
        assert status_code == 200
        assert response_body == '"{}"'

    @responses.activate
    @mock.patch('integrated_channels.degreed2.client.Degreed2APIClient.fetch_degreed_course_id')
    @mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
    def test_assign_course_skills(self, mock_fetch_degreed_course_id):
        """
        ``assign_course_skills`` should use the appropriate URL for making API call.
        """
        payload = {
            "data": [
                {
                    "id": "Financial Technology",
                    "type": "skills"
                }
            ]
        }
        test_course_key = 'a_course_id'
        mock_fetch_degreed_course_id.return_value = test_course_key
        enterprise_config = factories.Degreed2EnterpriseCustomerConfigurationFactory()
        degreed_api_client = Degreed2APIClient(enterprise_config)
        oauth_url = degreed_api_client.get_oauth_url()

        responses.add(
            responses.POST,
            oauth_url,
            json=self.expected_token_response_body,
            status=200
        )
        responses.add(
            responses.PATCH,
            f'{degreed_api_client.get_course_skills_url(test_course_key)}',
            json='{}',
            status=201
        )

        status_code, response_body = degreed_api_client.assign_course_skills('edx_course_key', payload)
        assert len(responses.calls) == 2
        assert responses.calls[0].request.url == oauth_url
        assert responses.calls[1].request.url == f'{degreed_api_client.get_course_skills_url(test_course_key)}'
        assert status_code == 201
        assert response_body == '"{}"'

    @responses.activate
    @mock.patch('integrated_channels.degreed2.client.Degreed2APIClient.fetch_degreed_course_id')
    def test_assign_skills_api_connection_error(self, mock_fetch_degreed_course_id):
        """
        ``assign_course_skills`` should raise ClientError when API request fails with a connection error.
        """
        test_course_key = 'a_course_id'
        mock_fetch_degreed_course_id.return_value = test_course_key
        enterprise_config = factories.Degreed2EnterpriseCustomerConfigurationFactory()
        degreed_api_client = Degreed2APIClient(enterprise_config)
        oauth_url = degreed_api_client.get_oauth_url()

        responses.add(
            responses.POST,
            oauth_url,
            json=self.expected_token_response_body,
            status=200
        )
        responses.add(
            responses.PATCH,
            f'{degreed_api_client.get_course_skills_url(test_course_key)}',
            body=requests.exceptions.RequestException()
        )

        payload = {
            "data": [
                {
                    "id": "Financial Technology",
                    "type": "skills"
                }
            ]
        }
        with pytest.raises(ClientError):
            degreed_api_client.assign_course_skills('edx_course_key', payload)

    @responses.activate
    @mock.patch('integrated_channels.degreed2.client.Degreed2APIClient.fetch_degreed_course_id')
    def test_assign_skills_api_failure_response(self, mock_fetch_degreed_course_id):
        """
        ``assign_course_skills`` should raise ClientError when API request fails with a with status code above 400.
        """
        test_course_key = 'a_course_id'
        mock_fetch_degreed_course_id.return_value = test_course_key
        enterprise_config = factories.Degreed2EnterpriseCustomerConfigurationFactory()
        degreed_api_client = Degreed2APIClient(enterprise_config)
        oauth_url = degreed_api_client.get_oauth_url()

        responses.add(
            responses.POST,
            oauth_url,
            json=self.expected_token_response_body,
            status=200
        )
        responses.add(
            responses.PATCH,
            f'{degreed_api_client.get_course_skills_url(test_course_key)}',
            json='{}',
            status=400
        )

        payload = {
            "data": [
                {
                    "id": "Financial Technology",
                    "type": "skills"
                }
            ]
        }
        with pytest.raises(ClientError):
            degreed_api_client.assign_course_skills('edx_course_key', payload)

    @responses.activate
    @mock.patch('integrated_channels.degreed2.client.Degreed2APIClient.fetch_degreed_course_id')
    @mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
    def test_update_content_metadata_retry_success(self, mock_fetch_degreed_course_id):
        """
        ``update_content_metadata`` should use the appropriate URLs for transmission.
        """
        mock_fetch_degreed_course_id.return_value = 'a_course_id'
        enterprise_config = factories.Degreed2EnterpriseCustomerConfigurationFactory()
        degreed_api_client = Degreed2APIClient(enterprise_config)
        oauth_url = degreed_api_client.get_oauth_url()
        degreed_course_id = 'a_course_id'
        course_url = degreed_api_client.get_courses_url()

        responses.add(
            responses.POST,
            oauth_url,
            json=self.expected_token_response_body,
            status=200
        )
        responses.add(
            responses.PATCH,
            f'{degreed_api_client.get_courses_url()}/a_course_id',
            json=self.too_fast_response,
            status=429
        )
        responses.add(
            responses.PATCH,
            f'{degreed_api_client.get_courses_url()}/a_course_id',
            json='{}',
            status=200
        )
        responses.add(
            responses.GET,
            EnterpriseCatalogApiClient.API_BASE_URL
            + EnterpriseCatalogApiClient.CONTENT_METADATA_IDENTIFIER_ENDPOINT.format(
                enterprise_config.enterprise_customer.uuid, "key/"
            ),
            json={"skill_names": ["Supply Chain", "Supply Chain Management"]},
            status=200,
        )
        responses.add(
            responses.GET,
            course_url + "?filter%5Bexternal_id%5D=key",
            json={"data": [{"id": degreed_course_id}]},
            status=200,
        )
        responses.add(
            responses.PATCH,
            f'{enterprise_config.degreed_base_url}api/v2/content/{degreed_course_id}/relationships/skills',
            json='{}',
            status=200
        )
        status_code, response_body = degreed_api_client.update_content_metadata(create_course_payload())
        assert len(responses.calls) == 5
        assert responses.calls[0].request.url == oauth_url
        assert responses.calls[1].request.url == f'{degreed_api_client.get_courses_url()}/a_course_id'
        assert responses.calls[2].request.url == f'{degreed_api_client.get_courses_url()}/a_course_id'
        assert status_code == 200
        assert response_body == '"{}"'

    @responses.activate
    @mock.patch('integrated_channels.degreed2.client.Degreed2APIClient.fetch_degreed_course_id')
    @mock.patch('enterprise.api_client.client.JwtBuilder', mock.Mock())
    def test_update_content_metadata_retry_exhaust(self, mock_fetch_degreed_course_id):
        """
        ``update_content_metadata`` should use the appropriate URLs for transmission.
        """
        mock_fetch_degreed_course_id.return_value = 'a_course_id'
        enterprise_config = factories.Degreed2EnterpriseCustomerConfigurationFactory()
        degreed_api_client = Degreed2APIClient(enterprise_config)
        oauth_url = degreed_api_client.get_oauth_url()
        degreed_course_id = 'a_course_id'
        course_url = degreed_api_client.get_courses_url()

        responses.add(
            responses.POST,
            oauth_url,
            json=self.expected_token_response_body,
            status=200
        )
        responses.add(
            responses.PATCH,
            f'{degreed_api_client.get_courses_url()}/a_course_id',
            json=self.too_fast_response,
            status=429
        )
        responses.add(
            responses.PATCH,
            f'{degreed_api_client.get_courses_url()}/a_course_id',
            json=self.too_fast_response,
            status=429
        )
        responses.add(
            responses.PATCH,
            f'{degreed_api_client.get_courses_url()}/a_course_id',
            json=self.too_fast_response,
            status=429
        )
        responses.add(
            responses.PATCH,
            f'{degreed_api_client.get_courses_url()}/a_course_id',
            json=self.too_fast_response,
            status=429
        )
        responses.add(
            responses.PATCH,
            f'{degreed_api_client.get_courses_url()}/a_course_id',
            json=self.too_fast_response,
            status=429
        )
        responses.add(
            responses.GET,
            EnterpriseCatalogApiClient.API_BASE_URL
            + EnterpriseCatalogApiClient.CONTENT_METADATA_IDENTIFIER_ENDPOINT.format(
                enterprise_config.enterprise_customer.uuid, "key/"
            ),
            json={"skill_names": ["Supply Chain", "Supply Chain Management"]},
            status=200,
        )
        responses.add(
            responses.GET,
            course_url + "?filter%5Bexternal_id%5D=key",
            json={"data": [{"id": degreed_course_id}]},
            status=200,
        )
        responses.add(
            responses.PATCH,
            f'{enterprise_config.degreed_base_url}api/v2/content/{degreed_course_id}/relationships/skills',
            json='{}',
            status=200
        )

        status_code, response_body = degreed_api_client.update_content_metadata(create_course_payload())
        assert len(responses.calls) == 8
        assert responses.calls[0].request.url == oauth_url
        assert responses.calls[1].request.url == f'{degreed_api_client.get_courses_url()}/a_course_id'
        assert responses.calls[2].request.url == f'{degreed_api_client.get_courses_url()}/a_course_id'
        assert responses.calls[3].request.url == f'{degreed_api_client.get_courses_url()}/a_course_id'
        assert responses.calls[4].request.url == f'{degreed_api_client.get_courses_url()}/a_course_id'
        assert responses.calls[5].request.url == f'{degreed_api_client.get_courses_url()}/a_course_id'
        assert status_code == 429
        assert json.loads(response_body) == self.too_fast_response

    @responses.activate
    @mock.patch('integrated_channels.degreed2.client.Degreed2APIClient.fetch_degreed_course_id')
    def test_delete_content_metadata(self, mock_fetch_degreed_course_id):
        """
        ``delete_content_metadata`` should use the appropriate URLs for transmission.
        """
        mock_fetch_degreed_course_id.return_value = 'a_course_id'
        enterprise_config = factories.Degreed2EnterpriseCustomerConfigurationFactory()
        degreed_api_client = Degreed2APIClient(enterprise_config)
        oauth_url = degreed_api_client.get_oauth_url()

        responses.add(
            responses.POST,
            oauth_url,
            json=self.expected_token_response_body,
            status=200
        )
        responses.add(
            responses.DELETE,
            f'{degreed_api_client.get_courses_url()}/a_course_id',
            json='{}',
            status=200
        )

        status_code, response_body = degreed_api_client.delete_content_metadata(create_course_payload())
        assert len(responses.calls) == 2
        assert responses.calls[0].request.url == oauth_url
        assert responses.calls[1].request.url == f'{degreed_api_client.get_courses_url()}/a_course_id'
        assert status_code == 200
        assert response_body == '"{}"'

    @responses.activate
    @mock.patch('integrated_channels.degreed2.client.Degreed2APIClient.fetch_degreed_course_id')
    def test_delete_content_metadata_retry_success(self, mock_fetch_degreed_course_id):
        """
        ``delete_content_metadata`` should use the appropriate URLs for transmission.
        """
        mock_fetch_degreed_course_id.return_value = 'a_course_id'
        enterprise_config = factories.Degreed2EnterpriseCustomerConfigurationFactory()
        degreed_api_client = Degreed2APIClient(enterprise_config)
        oauth_url = degreed_api_client.get_oauth_url()

        responses.add(
            responses.POST,
            oauth_url,
            json=self.expected_token_response_body,
            status=200
        )
        responses.add(
            responses.DELETE,
            f'{degreed_api_client.get_courses_url()}/a_course_id',
            json=self.too_fast_response,
            status=429
        )
        responses.add(
            responses.DELETE,
            f'{degreed_api_client.get_courses_url()}/a_course_id',
            json='{}',
            status=200
        )

        status_code, response_body = degreed_api_client.delete_content_metadata(create_course_payload())
        assert len(responses.calls) == 3
        assert responses.calls[0].request.url == oauth_url
        assert responses.calls[1].request.url == f'{degreed_api_client.get_courses_url()}/a_course_id'
        assert responses.calls[2].request.url == f'{degreed_api_client.get_courses_url()}/a_course_id'
        assert status_code == 200
        assert response_body == '"{}"'

    @responses.activate
    @mock.patch('integrated_channels.degreed2.client.Degreed2APIClient.fetch_degreed_course_id')
    def test_delete_content_metadata_retry_exhaust(self, mock_fetch_degreed_course_id):
        """
        ``delete_content_metadata`` should use the appropriate URLs for transmission.
        """
        mock_fetch_degreed_course_id.return_value = 'a_course_id'
        enterprise_config = factories.Degreed2EnterpriseCustomerConfigurationFactory()
        degreed_api_client = Degreed2APIClient(enterprise_config)
        oauth_url = degreed_api_client.get_oauth_url()

        responses.add(
            responses.POST,
            oauth_url,
            json=self.expected_token_response_body,
            status=200
        )
        responses.add(
            responses.DELETE,
            f'{degreed_api_client.get_courses_url()}/a_course_id',
            json=self.too_fast_response,
            status=429
        )
        responses.add(
            responses.DELETE,
            f'{degreed_api_client.get_courses_url()}/a_course_id',
            json=self.too_fast_response,
            status=429
        )
        responses.add(
            responses.DELETE,
            f'{degreed_api_client.get_courses_url()}/a_course_id',
            json=self.too_fast_response,
            status=429
        )
        responses.add(
            responses.DELETE,
            f'{degreed_api_client.get_courses_url()}/a_course_id',
            json=self.too_fast_response,
            status=429
        )

        with pytest.raises(ClientError):
            status_code, response_body = degreed_api_client.delete_content_metadata(create_course_payload())
            assert len(responses.calls) == 5
            assert responses.calls[0].request.url == oauth_url
            assert responses.calls[1].request.url == f'{degreed_api_client.get_courses_url()}/a_course_id'
            assert responses.calls[2].request.url == f'{degreed_api_client.get_courses_url()}/a_course_id'
            assert responses.calls[3].request.url == f'{degreed_api_client.get_courses_url()}/a_course_id'
            assert responses.calls[4].request.url == f'{degreed_api_client.get_courses_url()}/a_course_id'
            assert status_code == 429
            assert json.loads(response_body) == self.too_fast_response

    @responses.activate
    def test_degreed_api_connection_error(self):
        """
        ``create_content_metadata`` should raise ClientError when API request fails with a connection error.
        """
        degreed_api_client = Degreed2APIClient(self.enterprise_config)
        responses.add(
            responses.POST,
            degreed_api_client.get_oauth_url(),
            json=self.expected_token_response_body,
            status=200
        )
        responses.add(
            responses.POST,
            self.course_url,
            body=requests.exceptions.RequestException()
        )

        payload = create_course_payload()
        with pytest.raises(ClientError):
            degreed_api_client.create_content_metadata(payload)

    @responses.activate
    def test_degreed_api_application_error(self):
        """
        ``create_content_metadata`` should raise ClientError when API request fails with an application error.
        """
        degreed_api_client = Degreed2APIClient(self.enterprise_config)
        responses.add(
            responses.POST,
            degreed_api_client.get_oauth_url(),
            json=self.expected_token_response_body,
            status=200
        )
        responses.add(
            responses.POST,
            self.course_url,
            json={'message': 'error'},
            status=400
        )

        payload = create_course_payload()
        with pytest.raises(ClientError):
            degreed_api_client.create_content_metadata(payload)

    @responses.activate
    def test_expired_token(self):
        """
        If our token expires after some call, make sure to get it again.

        Make a call, have the token expire after waiting some time (technically no time since time is frozen),
        and make a call again and notice 2 OAuth calls in total are required.
        """
        degreed_api_client = Degreed2APIClient(self.enterprise_config)
        responses.add(
            responses.POST,
            degreed_api_client.get_oauth_url(),
            json={"expires_in": 0, "access_token": self.access_token},
            status=200
        )

        degreed_api_client._create_session('scope')  # pylint: disable=protected-access
        degreed_api_client._create_session('scope')  # pylint: disable=protected-access
        assert len(responses.calls) == 2
        assert responses.calls[0].request.url == degreed_api_client.get_oauth_url()
        assert responses.calls[1].request.url == degreed_api_client.get_oauth_url()

    @responses.activate
    def test_existing_token_is_valid(self):
        """
        On a second call in the same session, if the token isn't expired we shouldn't need to do another OAuth2 call.
        """
        degreed_api_client = Degreed2APIClient(self.enterprise_config)
        responses.add(
            responses.POST,
            degreed_api_client.get_oauth_url(),
            json=self.expected_token_response_body,
            status=200
        )

        degreed_api_client._create_session('scope')  # pylint: disable=protected-access
        degreed_api_client._create_session('scope')  # pylint: disable=protected-access
        assert len(responses.calls) == 1
        assert responses.calls[0].request.url == degreed_api_client.get_oauth_url()

    @responses.activate
    def test_oauth_response_missing_keys(self):
        """
        A ``requests.RequestException`` is raised when the call for an OAuth2 access token returns no data.
        """

        degreed_api_client = Degreed2APIClient(self.enterprise_config)
        responses.add(
            responses.POST,
            degreed_api_client.get_oauth_url(),
            json={},
            status=200
        )
        with pytest.raises(ClientError):
            degreed_api_client._get('http://test', 'scope')  # pylint: disable=protected-access
