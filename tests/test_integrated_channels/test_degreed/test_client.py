"""
Tests for clients in integrated_channels.
"""

import datetime
import json
import unittest
from urllib.parse import urljoin

import pytest
import requests
import responses
from freezegun import freeze_time

from integrated_channels.degreed.client import DegreedAPIClient
from integrated_channels.exceptions import ClientError
from test_utils import factories

NOW = datetime.datetime(2017, 1, 2, 3, 4, 5, tzinfo=datetime.timezone.utc)
NOW_TIMESTAMP_FORMATTED = NOW.strftime('%F')


@pytest.mark.django_db
@freeze_time(NOW)
class TestDegreedApiClient(unittest.TestCase):
    """
    Test Degreed API client methods.
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
        self.client_id = "client_id"
        self.client_secret = "client_secret"
        self.company_id = "company_id"
        self.user_id = "user_id"
        self.user_pass = "user_pass"
        self.expires_in = 1800
        self.access_token = "access_token"
        self.expected_token_response_body = {"expires_in": self.expires_in, "access_token": self.access_token}
        factories.DegreedGlobalConfigurationFactory(
            completion_status_api_path=self.completion_status_api_path,
            course_api_path=self.course_api_path,
            oauth_api_path=self.oauth_api_path,
        )
        self.enterprise_config = factories.DegreedEnterpriseCustomerConfigurationFactory(
            key=self.client_id,
            secret=self.client_secret,
            degreed_company_id=self.company_id,
            degreed_base_url=self.url_base,
            degreed_user_id=self.user_id,
            degreed_user_password=self.user_pass,
        )

    @responses.activate
    def test_oauth_with_non_json_response(self):
        """ Test  _get_oauth_access_token with non json type response"""
        with pytest.raises(ClientError):
            responses.add(
                responses.POST,
                self.oauth_url,
            )
            client = DegreedAPIClient(self.enterprise_config)
            client._get_oauth_access_token(  # pylint: disable=protected-access
                self.client_id,
                self.client_secret,
                self.user_id,
                self.user_pass,
                DegreedAPIClient.COMPLETION_PROVIDER_SCOPE
            )

    @responses.activate
    def test_create_course_completion(self):
        """
        ``create_course_completion`` should use the appropriate URLs for transmission.
        """
        responses.add(
            responses.POST,
            self.oauth_url,
            json=self.expected_token_response_body,
            status=200
        )
        responses.add(
            responses.POST,
            self.completion_status_url,
            json='{}',
            status=200
        )

        payload = {
            'orgCode': self.company_id,
            'completions': [{
                'employeeId': 'abc123',
                'id': "course-v1:ColumbiaX+DS101X+1T2016",
                'completionDate': NOW_TIMESTAMP_FORMATTED,
            }]
        }
        degreed_api_client = DegreedAPIClient(self.enterprise_config)
        output = degreed_api_client.create_course_completion('fake-user', json.dumps(payload))

        assert output == (200, '"{}"')
        assert len(responses.calls) == 2
        assert responses.calls[0].request.url == self.oauth_url
        assert responses.calls[1].request.url == self.completion_status_url

    @responses.activate
    def test_delete_course_completion(self):
        """
        ``delete_course_completion`` should use the appropriate URLs for transmission.
        """
        responses.add(
            responses.POST,
            self.oauth_url,
            json=self.expected_token_response_body,
            status=200
        )
        responses.add(
            responses.DELETE,
            self.completion_status_url,
            json='{}',
            status=200
        )

        payload = {
            'orgCode': self.company_id,
            'completions': [{
                'employeeId': 'abc123',
                'id': "course-v1:ColumbiaX+DS101X+1T2016",
            }]
        }
        degreed_api_client = DegreedAPIClient(self.enterprise_config)
        output = degreed_api_client.delete_course_completion('fake-user', json.dumps(payload))

        assert output == (200, '"{}"')
        assert len(responses.calls) == 2
        assert responses.calls[0].request.url == self.oauth_url
        assert responses.calls[1].request.url == self.completion_status_url

    @responses.activate
    def test_create_content_metadata(self):
        """
        ``create_content_metadata`` should use the appropriate URLs for transmission.
        """
        responses.add(
            responses.POST,
            self.oauth_url,
            json=self.expected_token_response_body,
            status=200
        )
        responses.add(
            responses.POST,
            self.course_url,
            json='{}',
            status=200
        )

        payload = {
            'orgCode': 'org-code',
            'providerCode': 'provider-code',
            'courses': [{
                'contentId': 'content-id',
                'authors': [],
                'categoryTags': [],
                'url': 'url',
                'imageUrl': 'image-url',
                'videoUrl': 'video-url',
                'title': 'title',
                'description': 'description',
                'difficulty': 'difficulty',
                'duration': 20,
                'publishDate': '2017-01-01',
                'format': 'format',
                'institution': 'institution',
                'costType': 'paid',
                'language': 'en'
            }],
        }
        degreed_api_client = DegreedAPIClient(self.enterprise_config)
        degreed_api_client.create_content_metadata(payload)
        assert len(responses.calls) == 2
        assert responses.calls[0].request.url == self.oauth_url
        assert responses.calls[1].request.url == self.course_url

    @responses.activate
    def test_update_content_metadata(self):
        """
        ``update_content_metadata`` should use the appropriate URLs for transmission.
        """
        responses.add(
            responses.POST,
            self.oauth_url,
            json=self.expected_token_response_body,
            status=200
        )
        responses.add(
            responses.POST,
            self.course_url,
            json='{}',
            status=200
        )

        payload = {
            'orgCode': 'org-code',
            'providerCode': 'provider-code',
            'courses': [{
                'contentId': 'content-id',
                'authors': [],
                'categoryTags': [],
                'url': 'url',
                'imageUrl': 'image-url',
                'videoUrl': 'video-url',
                'title': 'title',
                'description': 'description',
                'difficulty': 'difficulty',
                'duration': 20,
                'publishDate': '2017-01-01',
                'format': 'format',
                'institution': 'institution',
                'costType': 'paid',
                'language': 'en'
            }],
        }
        degreed_api_client = DegreedAPIClient(self.enterprise_config)
        degreed_api_client.update_content_metadata(payload)
        assert len(responses.calls) == 2
        assert responses.calls[0].request.url == self.oauth_url
        assert responses.calls[1].request.url == self.course_url

    @responses.activate
    def test_delete_content_metadata(self):
        """
        ``delete_content_metadata`` should use the appropriate URLs for transmission.
        """
        responses.add(
            responses.POST,
            self.oauth_url,
            json=self.expected_token_response_body,
            status=200
        )
        responses.add(
            responses.DELETE,
            self.course_url,
            json='{}',
            status=200
        )

        payload = {
            'orgCode': 'org-code',
            'providerCode': 'provider-code',
            'courses': [{
                'contentId': 'content-id',
            }],
        }
        degreed_api_client = DegreedAPIClient(self.enterprise_config)
        degreed_api_client.delete_content_metadata(payload)
        assert len(responses.calls) == 2
        assert responses.calls[0].request.url == self.oauth_url
        assert responses.calls[1].request.url == self.course_url

    @responses.activate
    def test_degreed_api_connection_error(self):
        """
        ``create_content_metadata`` should raise ClientError when API request fails with a connection error.
        """
        responses.add(
            responses.POST,
            self.oauth_url,
            json=self.expected_token_response_body,
            status=200
        )
        responses.add(
            responses.POST,
            self.course_url,
            body=requests.exceptions.RequestException()
        )

        payload = {
            'orgCode': 'org-code',
            'providerCode': 'provider-code',
            'courses': [{
                'contentId': 'content-id',
            }],
        }
        with pytest.raises(ClientError):
            degreed_api_client = DegreedAPIClient(self.enterprise_config)
            degreed_api_client.create_content_metadata(payload)

    @responses.activate
    def test_degreed_api_application_error(self):
        """
        ``create_content_metadata`` should raise ClientError when API request fails with an application error.
        """
        responses.add(
            responses.POST,
            self.oauth_url,
            json=self.expected_token_response_body,
            status=200
        )
        responses.add(
            responses.POST,
            self.course_url,
            json={'message': 'error'},
            status=400
        )

        payload = {
            'orgCode': 'org-code',
            'providerCode': 'provider-code',
            'courses': [{
                'contentId': 'content-id',
            }],
        }
        with pytest.raises(ClientError):
            degreed_api_client = DegreedAPIClient(self.enterprise_config)
            degreed_api_client.create_content_metadata(payload)

    @responses.activate
    def test_expired_token(self):
        """
        If our token expires after some call, make sure to get it again.

        Make a call, have the token expire after waiting some time (technically no time since time is frozen),
        and make a call again and notice 2 OAuth calls in total are required.
        """
        responses.add(
            responses.POST,
            self.oauth_url,
            json={"expires_in": 0, "access_token": self.access_token},
            status=200
        )
        responses.add(
            responses.DELETE,
            self.course_url,
            json='{}',
            status=200
        )

        payload = {
            'orgCode': 'org-code',
            'providerCode': 'provider-code',
            'courses': [{
                'contentId': 'content-id',
            }],
        }
        degreed_api_client = DegreedAPIClient(self.enterprise_config)
        degreed_api_client.delete_content_metadata(payload)
        degreed_api_client.delete_content_metadata(payload)
        assert len(responses.calls) == 4
        assert responses.calls[0].request.url == self.oauth_url
        assert responses.calls[1].request.url == self.course_url
        assert responses.calls[2].request.url == self.oauth_url
        assert responses.calls[3].request.url == self.course_url

    @responses.activate
    def test_existing_token_is_valid(self):
        """
        On a second call in the same session, if the token isn't expired we shouldn't need to do another OAuth2 call.
        """
        responses.add(
            responses.POST,
            self.oauth_url,
            json=self.expected_token_response_body,
            status=200
        )
        responses.add(
            responses.DELETE,
            self.course_url,
            json='{}',
            status=200
        )

        payload = {
            'orgCode': 'org-code',
            'providerCode': 'provider-code',
            'courses': [{
                'contentId': 'content-id',
            }],
        }
        degreed_api_client = DegreedAPIClient(self.enterprise_config)
        degreed_api_client.delete_content_metadata(payload)
        degreed_api_client.delete_content_metadata(payload)
        assert len(responses.calls) == 3
        assert responses.calls[0].request.url == self.oauth_url
        assert responses.calls[1].request.url == self.course_url
        assert responses.calls[2].request.url == self.course_url

    @responses.activate
    def test_oauth_response_missing_keys(self):
        """
        A ``requests.RequestException`` is raised when the call for an OAuth2 access token returns no data.
        """
        responses.add(
            responses.POST,
            self.oauth_url,
            json={},
            status=200
        )
        responses.add(
            responses.DELETE,
            self.course_url,
            json={},
            status=200
        )

        degreed_api_client = DegreedAPIClient(self.enterprise_config)
        with pytest.raises(ClientError):
            degreed_api_client.delete_content_metadata({})
