"""
Tests for enterprise.api_client.sso_orchestrator.py
"""
import json
from urllib.parse import urljoin
from uuid import uuid4

import responses
from rest_framework.reverse import reverse

from django.conf import settings

from enterprise.api_client import sso_orchestrator
from enterprise.utils import (
    get_sso_orchestrator_api_base_url,
    get_sso_orchestrator_configure_edx_oauth_path,
    get_sso_orchestrator_configure_path,
)
from test_utils.factories import EnterpriseCustomerFactory

TEST_ENTERPRISE_ID = '1840e1dc-59cf-4a78-82c5-c5bbc0b5df0f'
TEST_ENTERPRISE_SSO_CONFIG_UUID = uuid4()
TEST_ENTERPRISE_NAME = 'Test Enterprise'
SSO_ORCHESTRATOR_CONFIGURE_URL = urljoin(
    get_sso_orchestrator_api_base_url(),
    get_sso_orchestrator_configure_path()
)
SSO_ORCHESTRATOR_CONFIGURE_EDX_OAUTH_URL = urljoin(
    get_sso_orchestrator_api_base_url(),
    get_sso_orchestrator_configure_edx_oauth_path()
)


@responses.activate
def test_post_sso_configuration():
    """
    Test that the post_sso_configuration method makes a POST request to the SSO Orchestrator API. Verify that the
    request body contains the expected data, including the callback url.
    """
    responses.add(
        responses.POST,
        SSO_ORCHESTRATOR_CONFIGURE_URL,
        json={'samlServiceProviderInformation': {'spMetadataUrl': 'https://example.com'}},
    )
    client = sso_orchestrator.EnterpriseSSOOrchestratorApiClient()
    actual_response = client.configure_sso_orchestration_record(
        config_data={'uuid': TEST_ENTERPRISE_SSO_CONFIG_UUID},
        config_pk=TEST_ENTERPRISE_SSO_CONFIG_UUID,
        enterprise_data={'uuid': TEST_ENTERPRISE_ID, 'name': TEST_ENTERPRISE_NAME, 'slug': TEST_ENTERPRISE_NAME},
    )
    assert actual_response == 'https://example.com'
    responses.assert_call_count(count=1, url=SSO_ORCHESTRATOR_CONFIGURE_URL)

    sent_body_params = json.loads(responses.calls[0].request.body)
    assert sent_body_params['samlConfiguration'] == {'uuid': str(TEST_ENTERPRISE_SSO_CONFIG_UUID)}
    expected_callback_path = reverse(
        'enterprise-customer-sso-configuration-orchestration-complete',
        kwargs={'configuration_uuid': TEST_ENTERPRISE_SSO_CONFIG_UUID},
    )
    assert sent_body_params['callbackUrl'] == urljoin(settings.LMS_ROOT_URL, expected_callback_path)
    assert sent_body_params['enterprise'] == {
        'uuid': TEST_ENTERPRISE_ID,
        'name': TEST_ENTERPRISE_NAME,
        'slug': TEST_ENTERPRISE_NAME
    }


@responses.activate
def test_configure_edx_oauth():
    """
    Test the configure_edx_oauth method.
    """
    fake_enterprise_customer = EnterpriseCustomerFactory.stub()
    fake_org_id = 'foobar'
    responses.add(
        responses.POST,
        SSO_ORCHESTRATOR_CONFIGURE_EDX_OAUTH_URL,
        json={'orgId': fake_org_id, 'status': 200},
    )
    client = sso_orchestrator.EnterpriseSSOOrchestratorApiClient()

    # Call the method under test:
    actual_response = client.configure_edx_oauth(enterprise_customer=fake_enterprise_customer)

    assert actual_response == fake_org_id
    responses.assert_call_count(count=1, url=SSO_ORCHESTRATOR_CONFIGURE_EDX_OAUTH_URL)

    sent_body_params = json.loads(responses.calls[0].request.body)
    assert sent_body_params['enterpriseName'] == fake_enterprise_customer.name
    assert sent_body_params['enterpriseSlug'] == fake_enterprise_customer.slug
    assert sent_body_params['enterpriseUuid'] == str(fake_enterprise_customer.uuid)
