# -*- coding: utf-8 -*-
"""
Tests for the Consent application's API module.
"""

from __future__ import absolute_import, unicode_literals

import ddt
from consent.api.v1.views import DataSharingConsentView as DSCView
from rest_framework.reverse import reverse

from django.conf import settings

from test_utils import (
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
            factories.EnterpriseCourseEnrollmentFactory,
            [{
                'course_id': TEST_COURSE,
                'enterprise_customer_user__user_id': TEST_USER_ID,
                'enterprise_customer_user__enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer_user__enterprise_customer__enforce_data_sharing_consent': 'at_enrollment',
                'consent_granted': True
            }],
            {
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
            },
            {
                'error': DSCView.MISSING_REQUIRED_PARAMS_MSG.format(
                    username='',
                    course_id=TEST_COURSE,
                    enterprise_customer_uuid=TEST_UUID
                )
            },
            400
        ),
        # Missing `enterprise_customer` input.
        (
            factories.EnterpriseCourseEnrollmentFactory,
            [{
                'course_id': TEST_COURSE,
                'enterprise_customer_user__user_id': TEST_USER_ID,
                'enterprise_customer_user__enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer_user__enterprise_customer__enforce_data_sharing_consent': 'at_enrollment',
                'consent_granted': True
            }],
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
            },
            {
                'error': DSCView.MISSING_REQUIRED_PARAMS_MSG.format(
                    username=TEST_USERNAME,
                    course_id=TEST_COURSE,
                    enterprise_customer_uuid=None
                )
            },
            400
        ),
        # Missing `course_id` input.
        (
            factories.EnterpriseCourseEnrollmentFactory,
            [{
                'course_id': TEST_COURSE,
                'enterprise_customer_user__user_id': TEST_USER_ID,
                'enterprise_customer_user__enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer_user__enterprise_customer__enforce_data_sharing_consent': 'at_enrollment',
                'consent_granted': True
            }],
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
            },
            {
                'error': DSCView.MISSING_REQUIRED_PARAMS_MSG.format(
                    username=TEST_USERNAME,
                    course_id='',
                    enterprise_customer_uuid=TEST_UUID
                )
            },
            400
        ),
        # No consent in an enterprise course enrollment nor in an audit.
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
            404
        ),
        # Consent given for an enterprise course enrollment & enabled for customer at enrollment.
        (
            factories.EnterpriseCourseEnrollmentFactory,
            [{
                'course_id': TEST_COURSE,
                'enterprise_customer_user__user_id': TEST_USER_ID,
                'enterprise_customer_user__enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer_user__enterprise_customer__enforce_data_sharing_consent': 'at_enrollment',
                'consent_granted': True
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
        # Consent not given for an enterprise course enrollment & enabled for customer at enrollment.
        (
            factories.EnterpriseCourseEnrollmentFactory,
            [{
                'course_id': TEST_COURSE,
                'enterprise_customer_user__user_id': TEST_USER_ID,
                'enterprise_customer_user__enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer_user__enterprise_customer__enforce_data_sharing_consent': 'at_enrollment',
                'consent_granted': False
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
        # Consent not given for an enterprise course enrollment & not enabled for customer at enrollment.
        (
            factories.EnterpriseCourseEnrollmentFactory,
            [{
                'course_id': TEST_COURSE,
                'enterprise_customer_user__user_id': TEST_USER_ID,
                'enterprise_customer_user__enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer_user__enterprise_customer__enable_data_sharing_consent': False,
                'enterprise_customer_user__enterprise_customer__enforce_data_sharing_consent': 'at_enrollment',
                'consent_granted': True
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
        # Consent not given for an enterprise course enrollment & not enabled for customer at enrollment.
        (
            factories.EnterpriseCourseEnrollmentFactory,
            [{
                'course_id': TEST_COURSE,
                'enterprise_customer_user__user_id': TEST_USER_ID,
                'enterprise_customer_user__enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer_user__enterprise_customer__enable_data_sharing_consent': False,
                'enterprise_customer_user__enterprise_customer__enforce_data_sharing_consent': 'at_enrollment',
                'consent_granted': False
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
        # Consent given for an enterprise course enrollment & enabled for customer while externally managed.
        (
            factories.EnterpriseCourseEnrollmentFactory,
            [{
                'course_id': TEST_COURSE,
                'enterprise_customer_user__user_id': TEST_USER_ID,
                'enterprise_customer_user__enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer_user__enterprise_customer__enforce_data_sharing_consent': 'externally_managed',
                'consent_granted': True
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
        # Consent not given for an enterprise course enrollment & enabled for customer while externally managed.
        (
            factories.EnterpriseCourseEnrollmentFactory,
            [{
                'course_id': TEST_COURSE,
                'enterprise_customer_user__user_id': TEST_USER_ID,
                'enterprise_customer_user__enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer_user__enterprise_customer__enforce_data_sharing_consent': 'externally_managed',
                'consent_granted': False
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
        # Consent not given for an enterprise course enrollment & not enabled for customer (externally managed).
        (
            factories.EnterpriseCourseEnrollmentFactory,
            [{
                'course_id': TEST_COURSE,
                'enterprise_customer_user__user_id': TEST_USER_ID,
                'enterprise_customer_user__enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer_user__enterprise_customer__enable_data_sharing_consent': False,
                'enterprise_customer_user__enterprise_customer__enforce_data_sharing_consent': 'externally_managed',
                'consent_granted': True
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
        # Consent not given for an enterprise course enrollment & not enabled for customer (externally managed).
        (
            factories.EnterpriseCourseEnrollmentFactory,
            [{
                'course_id': TEST_COURSE,
                'enterprise_customer_user__user_id': TEST_USER_ID,
                'enterprise_customer_user__enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer_user__enterprise_customer__enable_data_sharing_consent': False,
                'enterprise_customer_user__enterprise_customer__enforce_data_sharing_consent': 'externally_managed',
                'consent_granted': False
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
        # Consent given for an audit where enterprise forces DSC at enrollment.
        (
            factories.UserDataSharingConsentAuditFactory,
            [{
                'user__user_id': TEST_USER_ID,
                'user__enterprise_customer__uuid': TEST_UUID,
                'user__enterprise_customer__enforce_data_sharing_consent': 'at_enrollment',
                'state': 'enabled'
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
        # Consent not given for an audit where enterprise forces DSC at enrollment.
        (
            factories.UserDataSharingConsentAuditFactory,
            [{
                'user__user_id': TEST_USER_ID,
                'user__enterprise_customer__uuid': TEST_UUID,
                'user__enterprise_customer__enforce_data_sharing_consent': 'at_enrollment',
                'state': 'disabled'
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
        # Consent given for an audit where enterprise disabled DSC at enrollment.
        (
            factories.UserDataSharingConsentAuditFactory,
            [{
                'user__user_id': TEST_USER_ID,
                'user__enterprise_customer__uuid': TEST_UUID,
                'user__enterprise_customer__enable_data_sharing_consent': False,
                'user__enterprise_customer__enforce_data_sharing_consent': 'at_enrollment',
                'state': 'enabled'
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
        # Consent not given for an audit where enterprise disabled DSC at enrollment.
        (
            factories.UserDataSharingConsentAuditFactory,
            [{
                'user__user_id': TEST_USER_ID,
                'user__enterprise_customer__uuid': TEST_UUID,
                'user__enterprise_customer__enable_data_sharing_consent': False,
                'user__enterprise_customer__enforce_data_sharing_consent': 'at_enrollment',
                'state': 'disabled'
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
        # Consent given for an audit where enterprise forces DSC (externally managed).
        (
            factories.UserDataSharingConsentAuditFactory,
            [{
                'user__user_id': TEST_USER_ID,
                'user__enterprise_customer__uuid': TEST_UUID,
                'user__enterprise_customer__enforce_data_sharing_consent': 'externally_managed',
                'state': 'enabled'
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
        # Consent not given for an audit where enterprise forces DSC (externally managed).
        (
            factories.UserDataSharingConsentAuditFactory,
            [{
                'user__user_id': TEST_USER_ID,
                'user__enterprise_customer__uuid': TEST_UUID,
                'user__enterprise_customer__enforce_data_sharing_consent': 'externally_managed',
                'state': 'disabled'
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
        # Consent given for an audit where enterprise disabled DSC (externally managed).
        (
            factories.UserDataSharingConsentAuditFactory,
            [{
                'user__user_id': TEST_USER_ID,
                'user__enterprise_customer__uuid': TEST_UUID,
                'user__enterprise_customer__enable_data_sharing_consent': False,
                'user__enterprise_customer__enforce_data_sharing_consent': 'externally_managed',
                'state': 'enabled'
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
        # Consent not given for an audit where enterprise disabled DSC (externally managed).
        (
            factories.UserDataSharingConsentAuditFactory,
            [{
                'user__user_id': TEST_USER_ID,
                'user__enterprise_customer__uuid': TEST_UUID,
                'user__enterprise_customer__enable_data_sharing_consent': False,
                'user__enterprise_customer__enforce_data_sharing_consent': 'externally_managed',
                'state': 'disabled'
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
        # Missing `username` input.
        (
            factories.EnterpriseCourseEnrollmentFactory,
            [{
                'course_id': TEST_COURSE,
                'enterprise_customer_user__user_id': TEST_USER_ID,
                'enterprise_customer_user__enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer_user__enterprise_customer__enforce_data_sharing_consent': 'at_enrollment',
                'consent_granted': True
            }],
            {
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
            },
            {
                'error': DSCView.MISSING_REQUIRED_PARAMS_MSG.format(
                    username='',
                    course_id=TEST_COURSE,
                    enterprise_customer_uuid=TEST_UUID
                )
            },
            400
        ),
        # Missing `enterprise_customer` input.
        (
            factories.EnterpriseCourseEnrollmentFactory,
            [{
                'course_id': TEST_COURSE,
                'enterprise_customer_user__user_id': TEST_USER_ID,
                'enterprise_customer_user__enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer_user__enterprise_customer__enforce_data_sharing_consent': 'at_enrollment',
                'consent_granted': True
            }],
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
            },
            {
                'error': DSCView.MISSING_REQUIRED_PARAMS_MSG.format(
                    username=TEST_USERNAME,
                    course_id=TEST_COURSE,
                    enterprise_customer_uuid=None
                )
            },
            400
        ),
        # Missing `course_id` input.
        (
            factories.EnterpriseCourseEnrollmentFactory,
            [{
                'course_id': TEST_COURSE,
                'enterprise_customer_user__user_id': TEST_USER_ID,
                'enterprise_customer_user__enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer_user__enterprise_customer__enforce_data_sharing_consent': 'at_enrollment',
                'consent_granted': True
            }],
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
            },
            {
                'error': DSCView.MISSING_REQUIRED_PARAMS_MSG.format(
                    username=TEST_USERNAME,
                    course_id='',
                    enterprise_customer_uuid=TEST_UUID
                )
            },
            400
        ),
        # No consent in an enterprise course enrollment (at enrollment).
        # Expect new consent resource to be created with consent provided (at enrollment).
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
                DSCView.CONSENT_GRANTED: True,
                DSCView.CONSENT_REQUIRED: False,
            },
            200
        ),
        # No consent in an enterprise course enrollment (at enrollment).
        # Expect new consent resource to be created with consent provided (at enrollment).
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
                DSCView.CONSENT_GRANTED: True,
                DSCView.CONSENT_REQUIRED: False,
            },
            200
        ),
        # No consent in an enterprise course enrollment (externally managed).
        # Expect new consent resource to be created with consent provided (externally managed).
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
                DSCView.CONSENT_GRANTED: True,
                DSCView.CONSENT_REQUIRED: False,
            },
            200
        ),
        # No consent in an enterprise course enrollment (externally managed).
        # Expect new consent resource to be created with consent provided (externally managed).
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
                DSCView.CONSENT_GRANTED: True,
                DSCView.CONSENT_REQUIRED: False,
            },
            200
        ),
        # Consent already given for an enterprise course enrollment (at enrollment).
        # Expect nothing to change.
        (
            factories.EnterpriseCourseEnrollmentFactory,
            [{
                'course_id': TEST_COURSE,
                'enterprise_customer_user__user_id': TEST_USER_ID,
                'enterprise_customer_user__enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer_user__enterprise_customer__enforce_data_sharing_consent': 'at_enrollment',
                'consent_granted': True
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
        # Consent not given for an enterprise course enrollment (at enrollment).
        # Expect consent to be given (at enrollment).
        (
            factories.EnterpriseCourseEnrollmentFactory,
            [{
                'course_id': TEST_COURSE,
                'enterprise_customer_user__user_id': TEST_USER_ID,
                'enterprise_customer_user__enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer_user__enterprise_customer__enforce_data_sharing_consent': 'at_enrollment',
                'consent_granted': False
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
        # Consent already given for an enterprise course enrollment (at enrollment).
        # Expect nothing to change.
        (
            factories.EnterpriseCourseEnrollmentFactory,
            [{
                'course_id': TEST_COURSE,
                'enterprise_customer_user__user_id': TEST_USER_ID,
                'enterprise_customer_user__enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer_user__enterprise_customer__enable_data_sharing_consent': False,
                'enterprise_customer_user__enterprise_customer__enforce_data_sharing_consent': 'at_enrollment',
                'consent_granted': True
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
        # Consent not given for an enterprise course enrollment (at enrollment).
        # Expect consent to be given (at enrollment).
        (
            factories.EnterpriseCourseEnrollmentFactory,
            [{
                'course_id': TEST_COURSE,
                'enterprise_customer_user__user_id': TEST_USER_ID,
                'enterprise_customer_user__enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer_user__enterprise_customer__enable_data_sharing_consent': False,
                'enterprise_customer_user__enterprise_customer__enforce_data_sharing_consent': 'at_enrollment',
                'consent_granted': False
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
        # Consent already given for an enterprise course enrollment (externally managed).
        # Expect nothing to change.
        (
            factories.EnterpriseCourseEnrollmentFactory,
            [{
                'course_id': TEST_COURSE,
                'enterprise_customer_user__user_id': TEST_USER_ID,
                'enterprise_customer_user__enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer_user__enterprise_customer__enforce_data_sharing_consent': 'externally_managed',
                'consent_granted': True
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
        # Consent not given for an enterprise course enrollment (externally managed).
        # Expect consent to be given (externally managed).
        (
            factories.EnterpriseCourseEnrollmentFactory,
            [{
                'course_id': TEST_COURSE,
                'enterprise_customer_user__user_id': TEST_USER_ID,
                'enterprise_customer_user__enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer_user__enterprise_customer__enforce_data_sharing_consent': 'externally_managed',
                'consent_granted': False
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
        # Consent already given for an enterprise course enrollment (externally managed).
        # Expect nothing to change.
        (
            factories.EnterpriseCourseEnrollmentFactory,
            [{
                'course_id': TEST_COURSE,
                'enterprise_customer_user__user_id': TEST_USER_ID,
                'enterprise_customer_user__enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer_user__enterprise_customer__enable_data_sharing_consent': False,
                'enterprise_customer_user__enterprise_customer__enforce_data_sharing_consent': 'externally_managed',
                'consent_granted': True
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
        # Consent not given for an enterprise course enrollment (externally managed).
        # Expect consent to be given (externally managed).
        (
            factories.EnterpriseCourseEnrollmentFactory,
            [{
                'course_id': TEST_COURSE,
                'enterprise_customer_user__user_id': TEST_USER_ID,
                'enterprise_customer_user__enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer_user__enterprise_customer__enable_data_sharing_consent': False,
                'enterprise_customer_user__enterprise_customer__enforce_data_sharing_consent': 'externally_managed',
                'consent_granted': False
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
    )
    @ddt.unpack
    def test_consent_api_post_endpoint(self, factory, items, request_body,
                                       expected_response_body, expected_status_code):
        if factory:
            create_items(factory, items)
        response = self.client.post(self.path, request_body)
        self._assert_expectations(response, expected_response_body, expected_status_code)
        # Assert that an enterprise course enrollment exists with consent provided.
        if expected_status_code == 200:
            self._assert_consent_provided(response)

    @ddt.data(
        # Missing `username` input.
        (
            factories.EnterpriseCourseEnrollmentFactory,
            [{
                'course_id': TEST_COURSE,
                'enterprise_customer_user__user_id': TEST_USER_ID,
                'enterprise_customer_user__enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer_user__enterprise_customer__enforce_data_sharing_consent': 'at_enrollment',
                'consent_granted': True
            }],
            {
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
            },
            {
                'error': DSCView.MISSING_REQUIRED_PARAMS_MSG.format(
                    username='',
                    course_id=TEST_COURSE,
                    enterprise_customer_uuid=TEST_UUID
                )
            },
            400
        ),
        # Missing `enterprise_customer` input.
        (
            factories.EnterpriseCourseEnrollmentFactory,
            [{
                'course_id': TEST_COURSE,
                'enterprise_customer_user__user_id': TEST_USER_ID,
                'enterprise_customer_user__enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer_user__enterprise_customer__enforce_data_sharing_consent': 'at_enrollment',
                'consent_granted': True
            }],
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_COURSE_ID: TEST_COURSE,
            },
            {
                'error': DSCView.MISSING_REQUIRED_PARAMS_MSG.format(
                    username=TEST_USERNAME,
                    course_id=TEST_COURSE,
                    enterprise_customer_uuid=None
                )
            },
            400
        ),
        # Missing `course_id` input.
        (
            factories.EnterpriseCourseEnrollmentFactory,
            [{
                'course_id': TEST_COURSE,
                'enterprise_customer_user__user_id': TEST_USER_ID,
                'enterprise_customer_user__enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer_user__enterprise_customer__enforce_data_sharing_consent': 'at_enrollment',
                'consent_granted': True
            }],
            {
                DSCView.REQUIRED_PARAM_USERNAME: TEST_USERNAME,
                DSCView.REQUIRED_PARAM_ENTERPRISE_CUSTOMER: TEST_UUID,
            },
            {
                'error': DSCView.MISSING_REQUIRED_PARAMS_MSG.format(
                    username=TEST_USERNAME,
                    course_id='',
                    enterprise_customer_uuid=TEST_UUID
                )
            },
            400
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
            factories.EnterpriseCourseEnrollmentFactory,
            [{
                'course_id': TEST_COURSE,
                'enterprise_customer_user__user_id': TEST_USER_ID,
                'enterprise_customer_user__enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer_user__enterprise_customer__enforce_data_sharing_consent': 'at_enrollment',
                'consent_granted': True
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
            factories.EnterpriseCourseEnrollmentFactory,
            [{
                'course_id': TEST_COURSE,
                'enterprise_customer_user__user_id': TEST_USER_ID,
                'enterprise_customer_user__enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer_user__enterprise_customer__enforce_data_sharing_consent': 'at_enrollment',
                'consent_granted': False
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
            factories.EnterpriseCourseEnrollmentFactory,
            [{
                'course_id': TEST_COURSE,
                'enterprise_customer_user__user_id': TEST_USER_ID,
                'enterprise_customer_user__enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer_user__enterprise_customer__enable_data_sharing_consent': False,
                'enterprise_customer_user__enterprise_customer__enforce_data_sharing_consent': 'at_enrollment',
                'consent_granted': True
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
            factories.EnterpriseCourseEnrollmentFactory,
            [{
                'course_id': TEST_COURSE,
                'enterprise_customer_user__user_id': TEST_USER_ID,
                'enterprise_customer_user__enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer_user__enterprise_customer__enable_data_sharing_consent': False,
                'enterprise_customer_user__enterprise_customer__enforce_data_sharing_consent': 'at_enrollment',
                'consent_granted': False
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
            factories.EnterpriseCourseEnrollmentFactory,
            [{
                'course_id': TEST_COURSE,
                'enterprise_customer_user__user_id': TEST_USER_ID,
                'enterprise_customer_user__enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer_user__enterprise_customer__enforce_data_sharing_consent': 'externally_managed',
                'consent_granted': True
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
            factories.EnterpriseCourseEnrollmentFactory,
            [{
                'course_id': TEST_COURSE,
                'enterprise_customer_user__user_id': TEST_USER_ID,
                'enterprise_customer_user__enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer_user__enterprise_customer__enforce_data_sharing_consent': 'externally_managed',
                'consent_granted': False
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
            factories.EnterpriseCourseEnrollmentFactory,
            [{
                'course_id': TEST_COURSE,
                'enterprise_customer_user__user_id': TEST_USER_ID,
                'enterprise_customer_user__enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer_user__enterprise_customer__enable_data_sharing_consent': False,
                'enterprise_customer_user__enterprise_customer__enforce_data_sharing_consent': 'externally_managed',
                'consent_granted': True
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
            factories.EnterpriseCourseEnrollmentFactory,
            [{
                'course_id': TEST_COURSE,
                'enterprise_customer_user__user_id': TEST_USER_ID,
                'enterprise_customer_user__enterprise_customer__uuid': TEST_UUID,
                'enterprise_customer_user__enterprise_customer__enable_data_sharing_consent': False,
                'enterprise_customer_user__enterprise_customer__enforce_data_sharing_consent': 'externally_managed',
                'consent_granted': False
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
