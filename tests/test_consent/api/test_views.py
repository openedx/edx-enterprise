# -*- coding: utf-8 -*-
"""
Tests for the Consent application's API module.
"""

from __future__ import absolute_import, unicode_literals

import ddt
import mock
from rest_framework.reverse import reverse

from django.conf import settings

from consent.api.v1.views import DataSharingConsentView as DSCView
from test_utils import (
    FAKE_UUIDS,
    TEST_COURSE,
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
        discovery_client_class = mock.patch('enterprise.models.CourseCatalogApiServiceClient')
        self.discovery_client = discovery_client_class.start().return_value
        self.discovery_client.is_course_in_catalog.return_value = True
        self.addCleanup(discovery_client_class.stop)
        super(TestConsentAPIViews, self).setUp()

    def create_user(self, username=TEST_USERNAME, password=TEST_PASSWORD, **kwargs):
        """
        Create a test user and set its password.
        """
        self.user = factories.UserFactory(username=username, is_active=True, is_staff=True, id=TEST_USER_ID)
        self.user.set_password(password)
        self.user.save()

    def _assert_expectations(self, response, expected_body, expected_status):
        """
        Assert that the response's status code and body match our expectations.
        """
        response_body = self.load_json(response.content)
        self.assertEqual(response.status_code, expected_status)
        self.assertEqual(response_body, expected_body)

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
    def test_consent_api_get_endpoint(self, factory, items, request_body, expected_response_body, expected_status_code):
        """Test an expectation against an action on any Consent API endpoint."""
        if factory:
            create_items(factory, items)
        response = self.client.get(self.path, request_body)
        self._assert_expectations(response, expected_response_body, expected_status_code)

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
    @mock.patch('consent.helpers.CourseCatalogApiServiceClient')
    def test_consent_api_get_program(
            self,
            factory,
            items,
            request_body,
            expected_response_body,
            expected_status_code,
            program_courses,
            catalog_client_class,
    ):
        """Test the expected behavior of the program consent GET endpoint."""
        api_catalog_client = catalog_client_class.return_value
        api_catalog_client.get_program_course_keys.return_value = program_courses
        enterprise_customer = factories.EnterpriseCustomerFactory(
            uuid=TEST_UUID,
            enforce_data_sharing_consent='at_enrollment'
        )
        for item in items:
            item.update(enterprise_customer=enterprise_customer)
        if factory:
            create_items(factory, items)

        response = self.client.get(self.path, request_body)
        api_catalog_client.get_program_course_keys.assert_called_once_with(request_body['program_uuid'])
        self._assert_expectations(response, expected_response_body, expected_status_code)

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
    @mock.patch('consent.helpers.CourseCatalogApiServiceClient')
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
            catalog_client_class,
    ):
        """Test the expected behavior of the program consent POST endpoint."""
        api_catalog_client = catalog_client_class.return_value
        api_catalog_client.get_program_course_keys.return_value = program_courses
        enterprise_customer = factories.EnterpriseCustomerFactory(**enterprise_kwargs)
        for item in items:
            item.update(enterprise_customer=enterprise_customer)
        if factory:
            create_items(factory, items)
        response = self.client.post(self.path, request_body)
        self._assert_expectations(response, expected_response_body, expected_status_code)
        for check in followup_checks:
            response = self.client.get(self.path, check['request'])
            self._assert_expectations(response, check['response'], 200)

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
    @mock.patch('consent.helpers.CourseCatalogApiServiceClient')
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
            catalog_client_class,
    ):
        """Test the expected behavior of the program consent DELETE endpoint."""
        api_catalog_client = catalog_client_class.return_value
        api_catalog_client.get_program_course_keys.return_value = program_courses
        enterprise_customer = factories.EnterpriseCustomerFactory(**enterprise_kwargs)
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
        create_items(factory, items)
        response = self.client.get(self.path, request_body)
        self._assert_expectations(response, expected_response_body, expected_status_code)

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
    def test_consent_api_post_endpoint(self, factory, items, request_body,
                                       expected_response_body, expected_status_code):
        if factory:
            create_items(factory, items)
        response = self.client.post(self.path, request_body)
        self._assert_expectations(response, expected_response_body, expected_status_code)

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
            expected_status_code
    ):
        self.discovery_client.is_course_in_catalog.return_value = False
        create_items(factory, items)
        response = self.client.post(self.path, request_body)
        self._assert_expectations(response, expected_response_body, expected_status_code)

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
    def test_consent_api_delete_endpoint(self, factory, items, request_body,
                                         expected_response_body, expected_status_code):
        if factory:
            create_items(factory, items)
        response = self.client.delete(self.path, request_body)
        self._assert_expectations(response, expected_response_body, expected_status_code)
        # Assert that an enterprise course enrollment exists without consent provided.
        if expected_status_code == 200:
            self._assert_consent_not_provided(response)

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
            expected_status_code
    ):
        self.discovery_client.is_course_in_catalog.return_value = False
        if factory:
            create_items(factory, items)
        response = self.client.delete(self.path, request_body)
        self._assert_expectations(response, expected_response_body, expected_status_code)
        # Assert that an enterprise course enrollment exists without consent provided.
        if expected_status_code == 200:
            self._assert_consent_not_provided(response)
