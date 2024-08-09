"""
Tests for the Consent application's API module.
"""

from unittest import mock

import ddt
from rest_framework.reverse import reverse

from django.conf import settings

from consent.api.v1.views import DataSharingConsentView as DSCView
from enterprise.models import EnterpriseCustomer
from test_utils import (
    FAKE_UUIDS,
    TEST_COURSE,
    TEST_COURSE_KEY,
    TEST_PASSWORD,
    TEST_USER_ID,
    TEST_USERNAME,
    TEST_UUID,
    APITest,
    create_items,
    factories,
)
from test_utils.mixins import ConsentMixin


@ddt.ddt
class TestConsentAPIViews(APITest, ConsentMixin):
    """
    Tests for the Consent application's Data Sharing API views.
    """

    endpoint_name = 'data_sharing_consent'
    path = settings.TEST_SERVER + reverse(endpoint_name)

    def setUp(self):
        discovery_client_class = mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
        self.discovery_client = discovery_client_class.start().return_value
        self.discovery_client.is_course_in_catalog.return_value = True
        self.addCleanup(discovery_client_class.stop)
        super().setUp()

    @staticmethod
    def create_user(username=TEST_USERNAME, password=TEST_PASSWORD, **kwargs):
        """
        Create a test user and set its password.
        """
        kwargs['is_staff'] = True
        kwargs['id'] = TEST_USER_ID
        return APITest.create_user(username=username, password=password, **kwargs)

    def _assert_expectations(self, response, expected_body, expected_status):
        """
        Assert that the response's status code and body match our expectations.
        """
        response_body = self.load_json(response.content)
        self.assertEqual(response.status_code, expected_status)
        self.assertEqual(response_body, expected_body)

    @mock.patch('enterprise.models.EnterpriseCatalogApiClient')
    @ddt.data(
        # Missing `username` input.
        (
            factories.DataSharingConsentFactory,
            [{}],
            {
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
            },
            {
                'error': DSCView.MISSING_REQUIRED_PARAMS_MSG.format("'username'")
            },
            400
        ),
        # Missing `enterprise_customer_uuid` input.
        (
            factories.DataSharingConsentFactory,
            [{}],
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
            },
            {
                'error': DSCView.MISSING_REQUIRED_PARAMS_MSG.format("'enterprise_customer_uuid'")
            },
            400
        ),
        # Missing `course_id` input.
        (
            factories.DataSharingConsentFactory,
            [{}],
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
            },
            {
                'error': DSCView.MISSING_REQUIRED_PARAMS_MSG.format("one of 'course_id' or 'program_uuid'")
            },
            400
        ),
        (
            None,
            [{}],
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
            },
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
                DSCView.CONSENT_EXISTS: False,
                DSCView.CONSENT_GRANTED: False,
                DSCView.CONSENT_REQUIRED: False,
            },
            200
        ),
        (
            factories.DataSharingConsentFactory,
            [{
                'username': TEST_USERNAME,
                'course_id': TEST_COURSE,
                'enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer__enforce_data_sharing_consent': 'at_enrollment',
            }],
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
            },
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
                DSCView.CONSENT_EXISTS: True,
                DSCView.CONSENT_GRANTED: True,
                DSCView.CONSENT_REQUIRED: False,
            },
            200
        ),
        (
            factories.DataSharingConsentFactory,
            [{
                'username': TEST_USERNAME,
                'course_id': TEST_COURSE,
                'enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer__enforce_data_sharing_consent': 'at_enrollment',
                'granted': False
            }],
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
            },
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
                DSCView.CONSENT_EXISTS: True,
                DSCView.CONSENT_GRANTED: False,
                DSCView.CONSENT_REQUIRED: True,
            },
            200
        ),
        (
            factories.DataSharingConsentFactory,
            [{
                'username': TEST_USERNAME,
                'course_id': TEST_COURSE,
                'enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer__enable_data_sharing_consent': False,
                'enterprise_customer__enforce_data_sharing_consent': 'at_enrollment',
            }],
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
            },
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
                DSCView.CONSENT_EXISTS: True,
                DSCView.CONSENT_GRANTED: True,
                DSCView.CONSENT_REQUIRED: False,
            },
            200
        ),
        (
            factories.DataSharingConsentFactory,
            [{
                'username': TEST_USERNAME,
                'course_id': TEST_COURSE,
                'enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer__enable_data_sharing_consent': False,
                'enterprise_customer__enforce_data_sharing_consent': 'at_enrollment',
                'granted': False
            }],
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
            },
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
                DSCView.CONSENT_EXISTS: True,
                DSCView.CONSENT_GRANTED: False,
                DSCView.CONSENT_REQUIRED: False,
            },
            200
        ),
        (
            factories.DataSharingConsentFactory,
            [{
                'username': TEST_USERNAME,
                'course_id': TEST_COURSE,
                'enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer__enforce_data_sharing_consent': 'externally_managed',
            }],
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
            },
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
                DSCView.CONSENT_EXISTS: True,
                DSCView.CONSENT_GRANTED: True,
                DSCView.CONSENT_REQUIRED: False,
            },
            200
        ),
        (
            factories.DataSharingConsentFactory,
            [{
                'username': TEST_USERNAME,
                'course_id': TEST_COURSE,
                'enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer__enforce_data_sharing_consent': 'externally_managed',
                'granted': False
            }],
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
            },
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
                DSCView.CONSENT_EXISTS: True,
                DSCView.CONSENT_GRANTED: False,
                DSCView.CONSENT_REQUIRED: False,
            },
            200
        ),
        (
            factories.DataSharingConsentFactory,
            [{
                'username': TEST_USERNAME,
                'course_id': TEST_COURSE,
                'enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer__enable_data_sharing_consent': False,
                'enterprise_customer__enforce_data_sharing_consent': 'externally_managed',
            }],
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
            },
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
                DSCView.CONSENT_EXISTS: True,
                DSCView.CONSENT_GRANTED: True,
                DSCView.CONSENT_REQUIRED: False,
            },
            200
        ),
        (
            factories.DataSharingConsentFactory,
            [{
                'username': TEST_USERNAME,
                'course_id': TEST_COURSE,
                'enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer__enable_data_sharing_consent': False,
                'enterprise_customer__enforce_data_sharing_consent': 'externally_managed',
                'granted': False
            }],
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
            },
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
                DSCView.CONSENT_EXISTS: True,
                DSCView.CONSENT_GRANTED: False,
                DSCView.CONSENT_REQUIRED: False,
            },
            200
        ),
    )
    @ddt.unpack
    def test_consent_api_get_endpoint(
            self,
            factory,
            items,
            request_body,
            expected_response_body,
            expected_status_code,
            catalog_api_client_mock,
    ):
        """Test an expectation against an action on any Consent API endpoint."""
        content_filter = {
            'key': [TEST_COURSE]
        }
        catalog_api_client_mock.return_value.contains_content_items.return_value = False
        self.discovery_client.get_course_id.return_value = TEST_COURSE_KEY
        if factory:
            create_items(factory, items)
        uuid = items[0].get('enterprise_customer__uuid')
        if uuid:
            enterprise_customer = EnterpriseCustomer.objects.get(uuid=uuid)
            factories.EnterpriseCustomerCatalogFactory(
                enterprise_customer=enterprise_customer,
                content_filter=content_filter
            )
        response = self.client.get(self.path, request_body)
        self._assert_expectations(response, expected_response_body, expected_status_code)

    @mock.patch('enterprise.models.EnterpriseCatalogApiClient')
    @ddt.data(
        (
            factories.DataSharingConsentFactory,
            [
                {
                    'username': TEST_USERNAME,
                    'course_id': 'org1+course',
                },
                {
                    'username': TEST_USERNAME,
                    'course_id': 'org2+othercourse',
                },
            ],
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_PROGRAM_UUID: 'fake-uuid',
            },
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_PROGRAM_UUID: 'fake-uuid',
                DSCView.CONSENT_EXISTS: True,
                DSCView.CONSENT_GRANTED: True,
                DSCView.CONSENT_REQUIRED: False,
            },
            200,
            ['org1+course', 'org2+othercourse']
        ),
        (
            None,
            [],
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_PROGRAM_UUID: 'fake-uuid',
            },
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_PROGRAM_UUID: 'fake-uuid',
                DSCView.CONSENT_EXISTS: False,
                DSCView.CONSENT_GRANTED: False,
                DSCView.CONSENT_REQUIRED: True,
            },
            200,
            ['org1+course', 'org2+othercourse']
        ),
        (
            factories.DataSharingConsentFactory,
            [
                {
                    'username': TEST_USERNAME,
                    'course_id': 'org1+course',
                },
                {
                    'username': TEST_USERNAME,
                    'course_id': 'org2+othercourse',
                },
            ],
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_PROGRAM_UUID: 'fake-uuid',
            },
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_PROGRAM_UUID: 'fake-uuid',
                DSCView.CONSENT_EXISTS: False,
                DSCView.CONSENT_GRANTED: False,
                DSCView.CONSENT_REQUIRED: False,
            },
            200,
            []
        ),
    )
    @ddt.unpack
    def test_consent_api_get_program(
            self,
            factory,
            items,
            request_body,
            expected_response_body,
            expected_status_code,
            program_courses,
            catalog_api_client_mock
    ):
        """Test the expected behavior of the program consent GET endpoint."""
        self.discovery_client.get_program_course_keys.return_value = program_courses
        enterprise_customer = factories.EnterpriseCustomerFactory(
            uuid=TEST_UUID,
            enforce_data_sharing_consent='at_enrollment'
        )
        content_filter = {
            'key': program_courses
        }
        factories.EnterpriseCustomerCatalogFactory(
            enterprise_customer=enterprise_customer,
            content_filter=content_filter
        )
        for item in items:
            item.update(enterprise_customer=enterprise_customer)
        if factory:
            create_items(factory, items)

        catalog_api_client_mock.return_value.contains_content_items.return_value = True
        response = self.client.get(self.path, request_body)
        self.discovery_client.get_program_course_keys.assert_called_once_with(request_body['program_uuid'])
        self._assert_expectations(response, expected_response_body, expected_status_code)

    @mock.patch('enterprise.models.EnterpriseCatalogApiClient')
    @ddt.data(
        (
            {
                'uuid': TEST_UUID,
                'enable_data_sharing_consent': True,
                'enforce_data_sharing_consent': 'at_enrollment'
            },
            None,
            [],
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_PROGRAM_UUID: 'fake-program',
            },
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_PROGRAM_UUID: 'fake-program',
                DSCView.CONSENT_EXISTS: True,
                DSCView.CONSENT_GRANTED: True,
                DSCView.CONSENT_REQUIRED: False,
            },
            [
                {
                    'request': {
                        DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                        DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                        DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
                    },
                    'response': {
                        DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                        DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                        DSCView.REQUIRED_PARAM_COURSE_ID: 'edX+DemoX',
                        DSCView.CONSENT_EXISTS: True,
                        DSCView.CONSENT_GRANTED: True,
                        DSCView.CONSENT_REQUIRED: False,
                    }
                },
                {
                    'request': {
                        DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                        DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                        DSCView.REQUIRED_PARAM_COURSE_ID: 'edX+DemoX',
                    },
                    'response': {
                        DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                        DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                        DSCView.REQUIRED_PARAM_COURSE_ID: 'edX+DemoX',
                        DSCView.CONSENT_EXISTS: True,
                        DSCView.CONSENT_GRANTED: True,
                        DSCView.CONSENT_REQUIRED: False,
                    }
                },
            ],
            200,
            ['edX+DemoX']
        ),
    )
    @ddt.unpack
    def test_consent_api_post_program_endpoint(
            self,
            enterprise_kwargs,
            factory,
            items,
            request_body,
            expected_response_body,
            followup_checks,
            expected_status_code,
            program_courses,
            catalog_api_client_mock
    ):
        """Test the expected behavior of the program consent POST endpoint."""
        content_filter = {
            'key': program_courses
        }
        self.discovery_client.get_program_course_keys.return_value = program_courses
        self.discovery_client.get_course_id.return_value = 'edX+DemoX'
        catalog_api_client_mock.return_value.contains_content_items.return_value = True
        enterprise_customer = factories.EnterpriseCustomerFactory(**enterprise_kwargs)
        factories.EnterpriseCustomerCatalogFactory(
            enterprise_customer=enterprise_customer,
            content_filter=content_filter
        )
        for item in items:
            item.update(enterprise_customer=enterprise_customer)
        if factory:
            create_items(factory, items)
        response = self.client.post(self.path, request_body)
        self._assert_expectations(response, expected_response_body, expected_status_code)
        for check in followup_checks:
            response = self.client.get(self.path, check['request'])
            self._assert_expectations(response, check['response'], 200)

    @mock.patch('enterprise.models.EnterpriseCatalogApiClient')
    @ddt.data(
        (
            {
                'uuid': TEST_UUID,
                'enable_data_sharing_consent': True,
                'enforce_data_sharing_consent': 'at_enrollment'
            },
            factories.DataSharingConsentFactory,
            [{
                'username': TEST_USERNAME,
                'course_id': 'edX+DemoX',
                'granted': True
            }],
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_PROGRAM_UUID: 'fake-program',
            },
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_PROGRAM_UUID: 'fake-program',
                DSCView.CONSENT_EXISTS: True,
                DSCView.CONSENT_GRANTED: False,
                DSCView.CONSENT_REQUIRED: True,
            },
            [
                {
                    'request': {
                        DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                        DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                        DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
                    },
                    'response': {
                        DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                        DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                        DSCView.REQUIRED_PARAM_COURSE_ID: 'edX+DemoX',
                        DSCView.CONSENT_EXISTS: True,
                        DSCView.CONSENT_GRANTED: False,
                        DSCView.CONSENT_REQUIRED: True,
                    }
                },
                {
                    'request': {
                        DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                        DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                        DSCView.REQUIRED_PARAM_COURSE_ID: 'edX+DemoX',
                    },
                    'response': {
                        DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                        DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                        DSCView.REQUIRED_PARAM_COURSE_ID: 'edX+DemoX',
                        DSCView.CONSENT_EXISTS: True,
                        DSCView.CONSENT_GRANTED: False,
                        DSCView.CONSENT_REQUIRED: True,
                    }
                },
            ],
            200,
            ['edX+DemoX']
        ),
    )
    @ddt.unpack
    def test_consent_api_delete_program_endpoint(
            self,
            enterprise_kwargs,
            factory,
            items,
            request_body,
            expected_response_body,
            followup_checks,
            expected_status_code,
            program_courses,
            catalog_api_client_mock
    ):
        """Test the expected behavior of the program consent DELETE endpoint."""
        self.discovery_client.get_program_course_keys.return_value = program_courses
        self.discovery_client.get_course_id.return_value = 'edX+DemoX'
        catalog_api_client_mock.return_value.contains_content_items.return_value = False
        enterprise_customer = factories.EnterpriseCustomerFactory(**enterprise_kwargs)
        content_filter = {
            'key': program_courses
        }
        factories.EnterpriseCustomerCatalogFactory(
            enterprise_customer=enterprise_customer,
            content_filter=content_filter
        )
        for item in items:
            item.update(enterprise_customer=enterprise_customer)
        if factory:
            create_items(factory, items)
        response = self.client.delete(self.path, request_body)
        self._assert_expectations(response, expected_response_body, expected_status_code)
        for check in followup_checks:
            response = self.client.get(self.path, check['request'])
            self._assert_expectations(response, check['response'], 200)

    @ddt.data(
        (
            factories.DataSharingConsentFactory,
            [{
                'username': TEST_USERNAME,
                'course_id': TEST_COURSE,
                'enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer__enable_data_sharing_consent': False,
                'enterprise_customer__enforce_data_sharing_consent': 'externally_managed',
                'granted': False
            }],
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
            },
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
                DSCView.CONSENT_EXISTS: True,
                DSCView.CONSENT_GRANTED: False,
                DSCView.CONSENT_REQUIRED: False,
            },
            200
        ),
    )
    @ddt.unpack
    def test_consent_api_get_endpoint_course_not_in_catalog(
            self,
            factory,
            items,
            request_body,
            expected_response_body,
            expected_status_code
    ):
        self.discovery_client.is_course_in_catalog.return_value = False
        self.discovery_client.get_course_id.return_value = TEST_COURSE_KEY
        create_items(factory, items)
        response = self.client.get(self.path, request_body)
        self._assert_expectations(response, expected_response_body, expected_status_code)

    @mock.patch('enterprise.models.EnterpriseCatalogApiClient')
    @ddt.data(
        # Missing `username` input.
        (
            factories.DataSharingConsentFactory,
            [{}],
            {
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
            },
            {
                'error': DSCView.MISSING_REQUIRED_PARAMS_MSG.format("'username'")
            },
            400
        ),
        # Missing `enterprise_customer_uuid` input.
        (
            factories.DataSharingConsentFactory,
            [{}],
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
            },
            {
                'error': DSCView.MISSING_REQUIRED_PARAMS_MSG.format("'enterprise_customer_uuid'")
            },
            400
        ),
        # Missing `course_id` input.
        (
            factories.DataSharingConsentFactory,
            [{}],
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
            },
            {
                'error': DSCView.MISSING_REQUIRED_PARAMS_MSG.format("one of 'course_id' or 'program_uuid'")
            },
            400
        ),
        # Invalid `enterprise_customer_uuid` input.
        (
            factories.DataSharingConsentFactory,
            [{
                'username': TEST_USERNAME,
                'course_id': TEST_COURSE,
                'enterprise_customer__uuid': TEST_UUID,
            }],
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: FAKE_UUIDS[0],
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
            },
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: FAKE_UUIDS[0],
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
                DSCView.CONSENT_EXISTS: False,
                DSCView.CONSENT_GRANTED: False,
                DSCView.CONSENT_REQUIRED: False,
            },
            200
        ),
        (
            factories.DataSharingConsentFactory,
            [{
                'username': TEST_USERNAME,
                'course_id': TEST_COURSE,
                'enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer__enforce_data_sharing_consent': 'at_enrollment',
            }],
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
            },
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
                DSCView.CONSENT_EXISTS: True,
                DSCView.CONSENT_GRANTED: True,
                DSCView.CONSENT_REQUIRED: False,
            },
            200
        ),
        (
            factories.EnterpriseCustomerUserFactory,
            [{
                'user_id': TEST_USER_ID,
                'enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer__enable_data_sharing_consent': False,
                'enterprise_customer__enforce_data_sharing_consent': 'at_enrollment',
            }],
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: FAKE_UUIDS[4],
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
            },
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: FAKE_UUIDS[4],
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
                DSCView.CONSENT_EXISTS: False,
                DSCView.CONSENT_GRANTED: False,
                DSCView.CONSENT_REQUIRED: False,
            },
            200
        ),
        (
            factories.EnterpriseCustomerUserFactory,
            [{
                'user_id': TEST_USER_ID,
                'enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer__enforce_data_sharing_consent': 'externally_managed',
            }],
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: FAKE_UUIDS[4],
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
            },
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: FAKE_UUIDS[4],
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
                DSCView.CONSENT_EXISTS: False,
                DSCView.CONSENT_GRANTED: False,
                DSCView.CONSENT_REQUIRED: False,
            },
            200
        ),
        (
            factories.EnterpriseCustomerUserFactory,
            [{
                'user_id': TEST_USER_ID,
                'enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer__enable_data_sharing_consent': False,
                'enterprise_customer__enforce_data_sharing_consent': 'externally_managed',
            }],
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: FAKE_UUIDS[4],
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
            },
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: FAKE_UUIDS[4],
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
                DSCView.CONSENT_EXISTS: False,
                DSCView.CONSENT_GRANTED: False,
                DSCView.CONSENT_REQUIRED: False,
            },
            200
        ),
        (
            factories.DataSharingConsentFactory,
            [{
                'username': TEST_USERNAME,
                'course_id': TEST_COURSE,
                'enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer__enforce_data_sharing_consent': 'at_enrollment',
            }],
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
            },
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
                DSCView.CONSENT_EXISTS: True,
                DSCView.CONSENT_GRANTED: True,
                DSCView.CONSENT_REQUIRED: False,
            },
            200
        ),
        (
            factories.DataSharingConsentFactory,
            [{
                'username': TEST_USERNAME,
                'course_id': TEST_COURSE,
                'enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer__enforce_data_sharing_consent': 'at_enrollment',
                'granted': False
            }],
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
            },
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
                DSCView.CONSENT_EXISTS: True,
                DSCView.CONSENT_GRANTED: True,
                DSCView.CONSENT_REQUIRED: False,
            },
            200
        ),
        (
            factories.DataSharingConsentFactory,
            [{
                'username': TEST_USERNAME,
                'course_id': TEST_COURSE,
                'enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer__enable_data_sharing_consent': False,
                'enterprise_customer__enforce_data_sharing_consent': 'at_enrollment',
            }],
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
            },
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
                DSCView.CONSENT_EXISTS: True,
                DSCView.CONSENT_GRANTED: True,
                DSCView.CONSENT_REQUIRED: False,
            },
            200
        ),
        (
            factories.DataSharingConsentFactory,
            [{
                'username': TEST_USERNAME,
                'course_id': TEST_COURSE,
                'enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer__enable_data_sharing_consent': False,
                'enterprise_customer__enforce_data_sharing_consent': 'at_enrollment',
                'granted': False
            }],
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
            },
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
                DSCView.CONSENT_EXISTS: True,
                DSCView.CONSENT_GRANTED: False,
                DSCView.CONSENT_REQUIRED: False,
            },
            200
        ),
        (
            factories.DataSharingConsentFactory,
            [{
                'username': TEST_USERNAME,
                'course_id': TEST_COURSE,
                'enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer__enforce_data_sharing_consent': 'externally_managed',
            }],
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
            },
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
                DSCView.CONSENT_EXISTS: True,
                DSCView.CONSENT_GRANTED: True,
                DSCView.CONSENT_REQUIRED: False,
            },
            200
        ),
        (
            factories.DataSharingConsentFactory,
            [{
                'username': TEST_USERNAME,
                'course_id': TEST_COURSE,
                'enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer__enforce_data_sharing_consent': 'externally_managed',
                'granted': False
            }],
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
            },
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
                DSCView.CONSENT_EXISTS: True,
                DSCView.CONSENT_GRANTED: False,
                DSCView.CONSENT_REQUIRED: False,
            },
            200
        ),
        (
            factories.DataSharingConsentFactory,
            [{
                'username': TEST_USERNAME,
                'course_id': TEST_COURSE,
                'enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer__enable_data_sharing_consent': False,
                'enterprise_customer__enforce_data_sharing_consent': 'externally_managed',
            }],
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
            },
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
                DSCView.CONSENT_EXISTS: True,
                DSCView.CONSENT_GRANTED: True,
                DSCView.CONSENT_REQUIRED: False,
            },
            200
        ),
        (
            factories.DataSharingConsentFactory,
            [{
                'username': TEST_USERNAME,
                'course_id': TEST_COURSE,
                'enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer__enable_data_sharing_consent': False,
                'enterprise_customer__enforce_data_sharing_consent': 'externally_managed',
                'granted': False
            }],
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
            },
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
                DSCView.CONSENT_EXISTS: True,
                DSCView.CONSENT_GRANTED: False,
                DSCView.CONSENT_REQUIRED: False,
            },
            200
        ),
    )
    @ddt.unpack
    def test_consent_api_post_endpoint(
            self,
            factory,
            items,
            request_body,
            expected_response_body,
            expected_status_code,
            catalog_api_client_mock
    ):
        content_filter = {
            'key': [TEST_COURSE]
        }
        catalog_api_client_mock.return_value.contains_content_items.return_value = True
        self.discovery_client.get_course_id.return_value = TEST_COURSE_KEY
        if factory:
            create_items(factory, items)
        uuid = items[0].get('enterprise_customer__uuid')
        if uuid:
            enterprise_customer = EnterpriseCustomer.objects.get(uuid=uuid)
            factories.EnterpriseCustomerCatalogFactory(
                enterprise_customer=enterprise_customer,
                content_filter=content_filter
            )
        response = self.client.post(self.path, request_body)
        self._assert_expectations(response, expected_response_body, expected_status_code)

    @mock.patch('enterprise.models.EnterpriseCatalogApiClient')
    @ddt.data(
        (
            factories.EnterpriseCustomerUserFactory,
            [{
                'user_id': TEST_USER_ID,
                'enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer__enforce_data_sharing_consent': 'at_enrollment',
            }],
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
            },
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
                DSCView.CONSENT_EXISTS: False,
                DSCView.CONSENT_GRANTED: False,
                DSCView.CONSENT_REQUIRED: False,
            },
            200
        ),
    )
    @ddt.unpack
    def test_consent_api_post_endpoint_course_not_in_catalog(
            self,
            factory,
            items,
            request_body,
            expected_response_body,
            expected_status_code,
            catalog_api_client_mock
    ):
        self.discovery_client.is_course_in_catalog.return_value = False
        self.discovery_client.get_course_id.return_value = TEST_COURSE_KEY
        catalog_api_client_mock.return_value.contains_content_items.return_value = False
        catalog_api_client_mock.return_value.enterprise_contains_content_items.return_value = False
        create_items(factory, items)
        response = self.client.post(self.path, request_body)
        self._assert_expectations(response, expected_response_body, expected_status_code)

    @mock.patch('enterprise.models.EnterpriseCatalogApiClient')
    @ddt.data(
        # Missing `username` input.
        (
            factories.DataSharingConsentFactory,
            [{}],
            {
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
            },
            {
                'error': DSCView.MISSING_REQUIRED_PARAMS_MSG.format("'username'")
            },
            400
        ),
        # Missing `enterprise_customer_uuid` input.
        (
            factories.DataSharingConsentFactory,
            [{}],
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
            },
            {
                'error': DSCView.MISSING_REQUIRED_PARAMS_MSG.format("'enterprise_customer_uuid'")
            },
            400
        ),
        # Missing `course_id` input.
        (
            factories.DataSharingConsentFactory,
            [{}],
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
            },
            {
                'error': DSCView.MISSING_REQUIRED_PARAMS_MSG.format("one of 'course_id' or 'program_uuid'")
            },
            400
        ),
        # Invalid `enterprise_customer_uuid` input.
        (
            factories.DataSharingConsentFactory,
            [{
                'username': TEST_USERNAME,
                'course_id': TEST_COURSE,
                'enterprise_customer__uuid': TEST_UUID,
            }],
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: FAKE_UUIDS[0],
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
            },
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: FAKE_UUIDS[0],
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
                DSCView.CONSENT_EXISTS: False,
                DSCView.CONSENT_GRANTED: False,
                DSCView.CONSENT_REQUIRED: False,
            },
            200
        ),
        (
            factories.EnterpriseCustomerUserFactory,
            [{
                'user_id': TEST_USER_ID,
                'enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer__enforce_data_sharing_consent': 'at_enrollment',
            }],
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
            },
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
                DSCView.CONSENT_EXISTS: True,
                DSCView.CONSENT_GRANTED: False,
                DSCView.CONSENT_REQUIRED: True,
            },
            200
        ),
        (
            factories.EnterpriseCustomerUserFactory,
            [{
                'user_id': TEST_USER_ID,
                'enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer__enable_data_sharing_consent': False,
                'enterprise_customer__enforce_data_sharing_consent': 'at_enrollment',
            }],
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
            },
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
                DSCView.CONSENT_EXISTS: True,
                DSCView.CONSENT_GRANTED: False,
                DSCView.CONSENT_REQUIRED: False,
            },
            200
        ),
        (
            factories.EnterpriseCustomerUserFactory,
            [{
                'user_id': TEST_USER_ID,
                'enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer__enforce_data_sharing_consent': 'externally_managed',
            }],
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
            },
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
                DSCView.CONSENT_EXISTS: True,
                DSCView.CONSENT_GRANTED: False,
                DSCView.CONSENT_REQUIRED: False,
            },
            200
        ),
        (
            factories.EnterpriseCustomerUserFactory,
            [{
                'user_id': TEST_USER_ID,
                'enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer__enable_data_sharing_consent': False,
                'enterprise_customer__enforce_data_sharing_consent': 'externally_managed',
            }],
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
            },
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
                DSCView.CONSENT_EXISTS: True,
                DSCView.CONSENT_GRANTED: False,
                DSCView.CONSENT_REQUIRED: False,
            },
            200
        ),
        (
            factories.DataSharingConsentFactory,
            [{
                'username': TEST_USERNAME,
                'course_id': TEST_COURSE,
                'enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer__enforce_data_sharing_consent': 'at_enrollment',
            }],
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
            },
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
                DSCView.CONSENT_EXISTS: True,
                DSCView.CONSENT_GRANTED: False,
                DSCView.CONSENT_REQUIRED: True,
            },
            200
        ),
        (
            factories.DataSharingConsentFactory,
            [{
                'username': TEST_USERNAME,
                'course_id': TEST_COURSE,
                'enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer__enforce_data_sharing_consent': 'at_enrollment',
                'granted': False
            }],
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
            },
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
                DSCView.CONSENT_EXISTS: True,
                DSCView.CONSENT_GRANTED: False,
                DSCView.CONSENT_REQUIRED: True,
            },
            200
        ),
        (
            factories.DataSharingConsentFactory,
            [{
                'username': TEST_USERNAME,
                'course_id': TEST_COURSE,
                'enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer__enable_data_sharing_consent': False,
                'enterprise_customer__enforce_data_sharing_consent': 'at_enrollment',
            }],
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
            },
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
                DSCView.CONSENT_EXISTS: True,
                DSCView.CONSENT_GRANTED: False,
                DSCView.CONSENT_REQUIRED: False,
            },
            200
        ),
        (
            factories.DataSharingConsentFactory,
            [{
                'username': TEST_USERNAME,
                'course_id': TEST_COURSE,
                'enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer__enable_data_sharing_consent': False,
                'enterprise_customer__enforce_data_sharing_consent': 'at_enrollment',
                'granted': False
            }],
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
            },
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
                DSCView.CONSENT_EXISTS: True,
                DSCView.CONSENT_GRANTED: False,
                DSCView.CONSENT_REQUIRED: False
            },
            200
        ),
        (
            factories.DataSharingConsentFactory,
            [{
                'username': TEST_USERNAME,
                'course_id': TEST_COURSE,
                'enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer__enforce_data_sharing_consent': 'externally_managed',
            }],
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
            },
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
                DSCView.CONSENT_EXISTS: True,
                DSCView.CONSENT_GRANTED: False,
                DSCView.CONSENT_REQUIRED: False
            },
            200
        ),
        (
            factories.DataSharingConsentFactory,
            [{
                'username': TEST_USERNAME,
                'course_id': TEST_COURSE,
                'enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer__enforce_data_sharing_consent': 'externally_managed',
                'granted': False
            }],
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
            },
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
                DSCView.CONSENT_EXISTS: True,
                DSCView.CONSENT_GRANTED: False,
                DSCView.CONSENT_REQUIRED: False
            },
            200
        ),
        (
            factories.DataSharingConsentFactory,
            [{
                'username': TEST_USERNAME,
                'course_id': TEST_COURSE,
                'enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer__enable_data_sharing_consent': False,
                'enterprise_customer__enforce_data_sharing_consent': 'externally_managed',
            }],
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
            },
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
                DSCView.CONSENT_EXISTS: True,
                DSCView.CONSENT_GRANTED: False,
                DSCView.CONSENT_REQUIRED: False
            },
            200
        ),
        (
            factories.DataSharingConsentFactory,
            [{
                'username': TEST_USERNAME,
                'course_id': TEST_COURSE,
                'enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer__enable_data_sharing_consent': False,
                'enterprise_customer__enforce_data_sharing_consent': 'externally_managed',
                'granted': False
            }],
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
            },
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
                DSCView.CONSENT_EXISTS: True,
                DSCView.CONSENT_GRANTED: False,
                DSCView.CONSENT_REQUIRED: False
            },
            200
        ),
    )
    @ddt.unpack
    def test_consent_api_delete_endpoint(
            self,
            factory,
            items,
            request_body,
            expected_response_body,
            expected_status_code,
            catalog_api_client_mock,
    ):
        catalog_api_client_mock.return_value.contains_content_items.return_value = True
        content_filter = {
            'key': [TEST_COURSE]
        }
        self.discovery_client.get_course_id.return_value = TEST_COURSE_KEY
        if factory:
            create_items(factory, items)

        uuid = items[0].get('enterprise_customer__uuid')
        if uuid:
            enterprise_customer = EnterpriseCustomer.objects.get(uuid=uuid)
            factories.EnterpriseCustomerCatalogFactory(
                enterprise_customer=enterprise_customer,
                content_filter=content_filter
            )
        response = self.client.delete(self.path, request_body)
        self._assert_expectations(response, expected_response_body, expected_status_code)
        # Assert that an enterprise course enrollment exists without consent provided.
        if expected_status_code == 200:
            self._assert_consent_not_provided(response)

    @mock.patch('enterprise.models.EnterpriseCatalogApiClient')
    @ddt.data(
        (
            factories.DataSharingConsentFactory,
            [{
                'username': TEST_USERNAME,
                'course_id': TEST_COURSE,
                'enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer__enforce_data_sharing_consent': 'at_enrollment',
                'granted': False
            }],
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
            },
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
                DSCView.CONSENT_EXISTS: True,
                DSCView.CONSENT_GRANTED: False,
                DSCView.CONSENT_REQUIRED: False,
            },
            200
        ),
    )
    @ddt.unpack
    def test_consent_api_delete_endpoint_course_not_in_catalog(
            self,
            factory,
            items,
            request_body,
            expected_response_body,
            expected_status_code,
            catalog_api_client_mock,
    ):
        catalog_api_client_mock.return_value.contains_content_items.return_value = False
        catalog_api_client_mock.return_value.enterprise_contains_content_items.return_value = False
        if factory:
            create_items(factory, items)
        response = self.client.delete(self.path, request_body)
        self._assert_expectations(response, expected_response_body, expected_status_code)
        # Assert that an enterprise course enrollment exists without consent provided.
        if expected_status_code == 200:
            self._assert_consent_not_provided(response)
