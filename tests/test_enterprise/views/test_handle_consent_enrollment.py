# -*- coding: utf-8 -*-
"""
Tests for the ``HandleConsentEnrollment`` view of the Enterprise app.
"""

from __future__ import absolute_import, unicode_literals

import ddt
import mock
from faker import Factory as FakerFactory
from pytest import mark

from django.core.urlresolvers import reverse
from django.test import Client, TestCase

from enterprise.models import EnterpriseCourseEnrollment
from enterprise.views import LMS_COURSEWARE_URL, LMS_DASHBOARD_URL, LMS_START_PREMIUM_COURSE_FLOW_URL
from six.moves.urllib.parse import urlencode  # pylint: disable=import-error
from test_utils.factories import (
    EnterpriseCustomerFactory,
    EnterpriseCustomerIdentityProviderFactory,
    EnterpriseCustomerUserFactory,
    UserFactory,
)


@mark.django_db
@ddt.ddt
class TestHandleConsentEnrollmentView(TestCase):
    """
    Test HandleConsentEnrollment.
    """

    def setUp(self):
        self.user = UserFactory.create(is_staff=True, is_active=True)
        self.user.set_password("QWERTY")
        self.user.save()
        self.client = Client()
        self.demo_course_id = 'course-v1:edX+DemoX+Demo_Course'
        self.dummy_demo_course_modes = [
            {
                "slug": "professional",
                "name": "Professional Track",
                "min_price": 100,
                "sku": "sku-audit",
            },
            {
                "slug": "audit",
                "name": "Audit Track",
                "min_price": 0,
                "sku": "sku-audit",
            },
        ]
        super(TestHandleConsentEnrollmentView, self).setUp()

    def _login(self):
        """
        Log user in.
        """
        assert self.client.login(username=self.user.username, password="QWERTY")

    def _setup_registry_mock(self, registry_mock, provider_id):
        """
        Sets up the SSO Registry object
        """
        registry_mock.get.return_value.configure_mock(provider_id=provider_id, drop_existing_session=False)

    @mock.patch('enterprise.views.ProgramDataExtender')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.utils.Registry')
    def test_handle_consent_enrollment_without_course_mode(
            self,
            registry_mock,
            *args
    ):  # pylint: disable=unused-argument
        """
        Verify that user is redirected to LMS dashboard in case there is
        no parameter `course_mode` in the request querystring.
        """
        course_id = self.demo_course_id
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
            enable_audit_enrollment=True,
        )
        faker = FakerFactory.create()
        provider_id = faker.slug()  # pylint: disable=no-member
        self._setup_registry_mock(registry_mock, provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=provider_id, enterprise_customer=enterprise_customer)
        self._login()
        handle_consent_enrollment_url = reverse(
            'enterprise_handle_consent_enrollment',
            args=[enterprise_customer.uuid, course_id],
        )
        response = self.client.get(handle_consent_enrollment_url)
        redirect_url = LMS_DASHBOARD_URL
        self.assertRedirects(response, redirect_url, fetch_redirect_response=False)

    @mock.patch('enterprise.views.ProgramDataExtender')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.utils.Registry')
    def test_handle_consent_enrollment_404(
            self,
            registry_mock,
            enrollment_api_client_mock,
            *args
    ):  # pylint: disable=unused-argument
        """
        Verify that user gets HTTP 404 response if there is no enterprise in
        database against the provided enterprise UUID or if enrollment API
        client is unable to get course modes for the provided course id.
        """
        course_id = self.demo_course_id
        enrollment_client = enrollment_api_client_mock.return_value
        enrollment_client.get_course_modes.return_value = {}
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
            enable_audit_enrollment=True,
        )
        faker = FakerFactory.create()
        provider_id = faker.slug()  # pylint: disable=no-member
        self._setup_registry_mock(registry_mock, provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=provider_id, enterprise_customer=enterprise_customer)
        self._login()
        handle_consent_enrollment_url = '{consent_enrollment_url}?{params}'.format(
            consent_enrollment_url=reverse(
                'enterprise_handle_consent_enrollment', args=[enterprise_customer.uuid, course_id]
            ),
            params=urlencode({'course_mode': 'professional'})
        )
        response = self.client.get(handle_consent_enrollment_url)
        assert response.status_code == 404

    @mock.patch('enterprise.views.ProgramDataExtender')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.utils.Registry')
    def test_handle_consent_enrollment_no_enterprise_user(
            self,
            registry_mock,
            enrollment_api_client_mock,
            *args
    ):  # pylint: disable=unused-argument
        """
        Verify that user gets HTTP 404 response if the user is not linked to
        the enterprise with the provided enterprise UUID or if enrollment API
        client is unable to get course modes for the provided course id.
        """
        course_id = self.demo_course_id
        enrollment_client = enrollment_api_client_mock.return_value
        enrollment_client.get_course_modes.return_value = self.dummy_demo_course_modes
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
            enable_audit_enrollment=True,
        )
        faker = FakerFactory.create()
        provider_id = faker.slug()  # pylint: disable=no-member
        self._setup_registry_mock(registry_mock, provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=provider_id, enterprise_customer=enterprise_customer)
        self._login()
        handle_consent_enrollment_url = '{consent_enrollment_url}?{params}'.format(
            consent_enrollment_url=reverse(
                'enterprise_handle_consent_enrollment', args=[enterprise_customer.uuid, course_id]
            ),
            params=urlencode({'course_mode': 'professional'})
        )
        response = self.client.get(handle_consent_enrollment_url)
        assert response.status_code == 404

    @mock.patch('enterprise.views.ProgramDataExtender')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.get_enterprise_customer_user')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.utils.Registry')
    def test_handle_consent_enrollment_with_invalid_course_mode(
            self,
            registry_mock,
            enrollment_api_client_mock,
            get_ec_user_mock,
            *args
    ):  # pylint: disable=unused-argument
        """
        Verify that user is redirected to LMS dashboard in case the provided
        course mode does not exist.
        """
        course_id = self.demo_course_id
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
            enable_audit_enrollment=True,
        )
        faker = FakerFactory.create()
        provider_id = faker.slug()  # pylint: disable=no-member
        self._setup_registry_mock(registry_mock, provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=provider_id, enterprise_customer=enterprise_customer)
        enterprise_customer_user = EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=enterprise_customer
        )
        enrollment_client = enrollment_api_client_mock.return_value
        enrollment_client.get_course_modes.return_value = self.dummy_demo_course_modes
        mocked_enterprise_customer_user = get_ec_user_mock.return_value
        mocked_enterprise_customer_user.return_value = enterprise_customer_user
        self._login()
        handle_consent_enrollment_url = '{consent_enrollment_url}?{params}'.format(
            consent_enrollment_url=reverse(
                'enterprise_handle_consent_enrollment', args=[enterprise_customer.uuid, course_id]
            ),
            params=urlencode({'course_mode': 'some-invalid-course-mode'})
        )
        response = self.client.get(handle_consent_enrollment_url)
        redirect_url = LMS_DASHBOARD_URL
        self.assertRedirects(response, redirect_url, fetch_redirect_response=False)

    @mock.patch('enterprise.views.ProgramDataExtender')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.utils.Registry')
    def test_handle_consent_enrollment_with_audit_course_mode(
            self,
            registry_mock,
            enrollment_api_client_mock,
            *args
    ):  # pylint: disable=unused-argument
        """
        Verify that user is redirected to course in case the provided
        course mode is audit track.
        """
        course_id = self.demo_course_id
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
            enable_audit_enrollment=True,
        )
        faker = FakerFactory.create()
        provider_id = faker.slug()  # pylint: disable=no-member
        self._setup_registry_mock(registry_mock, provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=provider_id, enterprise_customer=enterprise_customer)
        enterprise_customer_user = EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=enterprise_customer
        )
        enrollment_client = enrollment_api_client_mock.return_value
        enrollment_client.get_course_modes.return_value = self.dummy_demo_course_modes
        self._login()
        handle_consent_enrollment_url = '{consent_enrollment_url}?{params}'.format(
            consent_enrollment_url=reverse(
                'enterprise_handle_consent_enrollment', args=[enterprise_customer.uuid, course_id]
            ),
            params=urlencode({'course_mode': 'audit'})
        )
        response = self.client.get(handle_consent_enrollment_url)
        redirect_url = LMS_COURSEWARE_URL.format(course_id=course_id)
        self.assertRedirects(response, redirect_url, fetch_redirect_response=False)

        self.assertTrue(EnterpriseCourseEnrollment.objects.filter(
            enterprise_customer_user__enterprise_customer=enterprise_customer,
            enterprise_customer_user__user_id=enterprise_customer_user.user_id,
            course_id=course_id
        ).exists())

    @mock.patch('enterprise.views.ProgramDataExtender')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.utils.Registry')
    def test_handle_consent_enrollment_with_professional_course_mode(
            self,
            registry_mock,
            enrollment_api_client_mock,
            *args
    ):  # pylint: disable=unused-argument
        """
        Verify that user is redirected to course in case the provided
        course mode is audit track.
        """
        course_id = self.demo_course_id
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
            enable_audit_enrollment=True,
        )
        faker = FakerFactory.create()
        provider_id = faker.slug()  # pylint: disable=no-member
        self._setup_registry_mock(registry_mock, provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=provider_id, enterprise_customer=enterprise_customer)
        enterprise_customer_user = EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=enterprise_customer
        )
        enrollment_client = enrollment_api_client_mock.return_value
        enrollment_client.get_course_modes.return_value = self.dummy_demo_course_modes
        self._login()
        handle_consent_enrollment_url = '{consent_enrollment_url}?{params}'.format(
            consent_enrollment_url=reverse(
                'enterprise_handle_consent_enrollment', args=[enterprise_customer.uuid, course_id]
            ),
            params=urlencode({'course_mode': 'professional'})
        )
        response = self.client.get(handle_consent_enrollment_url)
        redirect_url = LMS_START_PREMIUM_COURSE_FLOW_URL.format(course_id=course_id)
        self.assertRedirects(response, redirect_url, fetch_redirect_response=False)

        self.assertTrue(EnterpriseCourseEnrollment.objects.filter(
            enterprise_customer_user__enterprise_customer=enterprise_customer,
            enterprise_customer_user__user_id=enterprise_customer_user.user_id,
            course_id=course_id
        ).exists())
