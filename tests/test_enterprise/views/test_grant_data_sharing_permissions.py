# -*- coding: utf-8 -*-
"""
Tests for the ``GrantDataSharingPermissions`` view of the Enterprise app.
"""

from __future__ import absolute_import, unicode_literals

import ddt
import mock
from pytest import mark

from django.conf import settings
from django.core.urlresolvers import reverse
from django.test import Client, TestCase

from enterprise.models import EnterpriseCourseEnrollment
from test_utils import fake_render
from test_utils.factories import (
    DataSharingConsentFactory,
    EnterpriseCustomerFactory,
    EnterpriseCustomerUserFactory,
    UserFactory,
)
from test_utils.mixins import MessagesMixin


@mark.django_db
@ddt.ddt
class TestGrantDataSharingPermissions(MessagesMixin, TestCase):
    """
    Test GrantDataSharingPermissions.
    """

    def setUp(self):
        self.user = UserFactory.create(is_staff=True, is_active=True)
        self.user.set_password("QWERTY")
        self.user.save()
        self.client = Client()
        super(TestGrantDataSharingPermissions, self).setUp()

    url = reverse('grant_data_sharing_permissions')

    def _login(self):
        """
        Log user in.
        """
        assert self.client.login(username=self.user.username, password="QWERTY")

    def _assert_enterprise_linking_messages(self, response, user_is_active=True):
        """
        Verify response messages for a learner when he/she is linked with an
        enterprise depending on whether the learner has activated the linked
        account.
        """
        response_messages = self._get_messages_from_response_cookies(response)
        if user_is_active:
            # Verify that request contains the expected success message when a
            # learner with activated account is linked with an enterprise
            self.assertEqual(len(response_messages), 1)
            self._assert_request_message(
                response_messages[0],
                'success',
                '<strong>Account created</strong> Thank you for creating an account with edX.'
            )
        else:
            # Verify that request contains the expected success message and an
            # info message when a learner with unactivated account is linked
            # with an enterprise.
            self.assertEqual(len(response_messages), 2)
            self._assert_request_message(
                response_messages[0],
                'success',
                '<strong>Account created</strong> Thank you for creating an account with edX.'
            )
            self._assert_request_message(
                response_messages[1],
                'info',
                '<strong>Activate your account</strong> Check your inbox for an activation email. '
                'You will not be able to log back into your account until you have activated it.'
            )

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.models.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.CourseApiClient')
    @ddt.data(
        (False, True),
        (False, False),
        (True, False),
    )
    @ddt.unpack
    def test_get_course_specific_consent(
            self,
            defer_creation,
            existing_course_enrollment,
            course_api_client_mock,
            course_catalog_api_client_mock,
            *args
    ):  # pylint: disable=unused-argument
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        course_catalog_api_client_mock.return_value.course_in_catalog.return_value = True
        client = course_api_client_mock.return_value
        client.get_course_details.return_value = {
            'name': 'edX Demo Course',
        }
        self._login()
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        ecu = EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=enterprise_customer
        )
        if existing_course_enrollment:
            EnterpriseCourseEnrollment.objects.create(
                enterprise_customer_user=ecu,
                course_id=course_id
            )
        params = {
            'enterprise_customer_uuid': str(enterprise_customer.uuid),
            'course_id': 'course-v1:edX+DemoX+Demo_Course',
            'next': 'https://google.com',
            'failure_url': 'https://facebook.com',
        }
        if defer_creation:
            params['defer_creation'] = True
        response = self.client.get(self.url, data=params)
        assert response.status_code == 200
        expected_prompt = (
            'To access this course, you must first consent to share your learning achievements '
            'with <b>Starfleet Academy</b>.'
        )
        expected_alert = (
            'In order to start this course and use your discount, <b>you must</b> consent to share your '
            'course data with Starfleet Academy.'
        )

        for key, value in {
                "platform_name": "Test platform",
                "platform_description": "Test description",
                "tagline": "High-quality online learning opportunities from the world's best universities",
                "header_logo_alt_text": "Test platform home page",
                "consent_request_prompt": expected_prompt,
                "requested_permissions_header": (
                    'Per the <a href="#consent-policy-dropdown-bar" '
                    'class="policy-dropdown-link background-input failure-link" id="policy-dropdown-link">'
                    'Data Sharing Policy</a>, <b>Starfleet Academy</b> would like to know about:'
                ),
                'confirmation_alert_prompt': expected_alert,
                'confirmation_alert_prompt_warning': '',
                'sharable_items_footer': (
                    'My permission applies only to data from courses or programs that are sponsored by '
                    'Starfleet Academy, and not to data from any Test platform courses or programs that '
                    'I take on my own. I understand that once I grant my permission to allow data to be shared '
                    'with Starfleet Academy, I may not withdraw my permission but I may elect to unenroll '
                    'from any courses that are sponsored by Starfleet Academy.'
                ),
                "course_id": "course-v1:edX+DemoX+Demo_Course",
                "redirect_url": "https://google.com",
                "course_specific": True,
                "defer_creation": defer_creation,
                "welcome_text": "Welcome to Test platform.",
                'sharable_items_note_header': 'Please note',
                'LMS_SEGMENT_KEY': settings.LMS_SEGMENT_KEY,
                'LMS_ROOT_URL': 'http://localhost:8000',
        }.items():
            assert response.context[key] == value  # pylint:disable=no-member

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.CourseApiClient')
    def test_get_course_specific_consent_invalid_get_params(
            self,
            course_api_client_mock,
            *args
    ):  # pylint: disable=unused-argument
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        client = course_api_client_mock.return_value
        client.get_course_details.return_value = {
            'name': 'edX Demo Course',
        }
        self._login()
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        ecu = EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=enterprise_customer
        )
        EnterpriseCourseEnrollment.objects.create(
            enterprise_customer_user=ecu,
            course_id=course_id
        )
        DataSharingConsentFactory(
            username=self.user.username,
            course_id=course_id,
            enterprise_customer=enterprise_customer,
        )
        params = {
            'course_id': 'course-v1:edX+DemoX+Demo_Course',
            'next': 'https://google.com',
            'defer_creation': True,
        }
        response = self.client.get(self.url, data=params)
        assert response.status_code == 404

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.CourseApiClient')
    def test_get_course_specific_consent_unauthenticated_user(
            self,
            course_api_client_mock,
            *args
    ):  # pylint: disable=unused-argument
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        client = course_api_client_mock.return_value
        client.get_course_details.return_value = {
            'name': 'edX Demo Course',
        }
        ecu = EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=enterprise_customer
        )
        EnterpriseCourseEnrollment.objects.create(
            enterprise_customer_user=ecu,
            course_id=course_id
        )
        DataSharingConsentFactory(
            username=self.user.username,
            course_id=course_id,
            enterprise_customer=enterprise_customer,
        )
        response = self.client.get(
            self.url + '?course_id=course-v1%3AedX%2BDemoX%2BDemo_Course&next=https%3A%2F%2Fgoogle.com'
        )
        assert response.status_code == 302
        self.assertRedirects(
            response,
            (
                '/accounts/login/?next=/enterprise/grant_data_sharing_permissions%3Fcourse_id%3Dcourse-v1'
                '%253AedX%252BDemoX%252BDemo_Course%26next%3Dhttps%253A%252F%252Fgoogle.com'
            ),
            fetch_redirect_response=False
        )

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.CourseApiClient')
    def test_get_course_specific_consent_bad_api_response(
            self,
            course_api_client_mock,
            *args
    ):  # pylint: disable=unused-argument
        self._login()
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        client = course_api_client_mock.return_value
        client.get_course_details.return_value = None
        ecu = EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=enterprise_customer
        )
        EnterpriseCourseEnrollment.objects.create(
            enterprise_customer_user=ecu,
            course_id=course_id
        )
        DataSharingConsentFactory(
            username=self.user.username,
            course_id=course_id,
            enterprise_customer=enterprise_customer,
        )
        response = self.client.get(
            self.url + '?course_id=course-v1%3AedX%2BDemoX%2BDemo_Course&next=https%3A%2F%2Fgoogle.com'
        )
        assert response.status_code == 404

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.models.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.CourseApiClient')
    def test_get_course_specific_consent_not_needed(
            self,
            course_api_client_mock,
            course_catalog_api_client_mock,
            *args
    ):  # pylint: disable=unused-argument
        self._login()
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        course_catalog_api_client = course_catalog_api_client_mock.return_value
        course_catalog_api_client.is_course_in_catalog.return_value = False
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        client = course_api_client_mock.return_value
        client.get_course_details.return_value = {
            'name': 'edX Demo Course',
        }
        ecu = EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=enterprise_customer
        )
        EnterpriseCourseEnrollment.objects.create(
            enterprise_customer_user=ecu,
            course_id=course_id,
        )
        DataSharingConsentFactory(
            username=self.user.username,
            course_id=course_id,
            enterprise_customer=enterprise_customer,
            granted=True
        )
        response = self.client.get(
            self.url + '?course_id=course-v1%3AedX%2BDemoX%2BDemo_Course&next=https%3A%2F%2Fgoogle.com'
        )
        assert response.status_code == 404

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.CourseApiClient')
    @mock.patch('enterprise.views.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.models.CourseCatalogApiServiceClient')
    @mock.patch('enterprise.views.reverse')
    @ddt.data(
        (True, True, '/successful_enrollment'),
        (False, True, '/successful_enrollment'),
        (True, False, '/failure_url'),
        (False, False, '/failure_url'),
    )
    @ddt.unpack
    def test_post_course_specific_consent(
            self,
            defer_creation,
            consent_provided,
            expected_redirect_url,
            reverse_mock,
            course_catalog_api_client_mock_1,
            course_catalog_api_client_mock_2,
            course_api_client_mock,
            *args
    ):  # pylint: disable=unused-argument,invalid-name
        self._login()
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        ecu = EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=enterprise_customer
        )
        EnterpriseCourseEnrollment.objects.create(
            enterprise_customer_user=ecu,
            course_id=course_id,
        )
        dsc = DataSharingConsentFactory(
            username=self.user.username,
            course_id=course_id,
            enterprise_customer=enterprise_customer,
            granted=consent_provided
        )
        course_catalog_api_client_mock_1.return_value.program_exists.return_value = True
        course_catalog_api_client_mock_2.return_value.is_course_in_catalog = True
        course_api_client_mock.return_value.get_course_details.return_value = {'name': 'edX Demo Course'}
        reverse_mock.return_value = '/dashboard'
        post_data = {
            'enterprise_customer_uuid': enterprise_customer.uuid,
            'course_id': course_id,
            'redirect_url': '/successful_enrollment',
            'failure_url': '/failure_url',
        }
        if defer_creation:
            post_data['defer_creation'] = True
        if consent_provided:
            post_data['data_sharing_consent'] = consent_provided

        resp = self.client.post(self.url, post_data)

        assert resp.url.endswith(expected_redirect_url)  # pylint: disable=no-member
        assert resp.status_code == 302
        if not defer_creation:
            assert dsc.granted is consent_provided

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.CourseApiClient')
    @mock.patch('enterprise.views.reverse')
    def test_post_course_specific_consent_no_user(
            self,
            reverse_mock,
            course_api_client_mock,
            *args
    ):  # pylint: disable=unused-argument
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        ecu = EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=enterprise_customer
        )
        EnterpriseCourseEnrollment.objects.create(
            enterprise_customer_user=ecu,
            course_id=course_id
        )
        DataSharingConsentFactory(
            username=self.user.username,
            course_id=course_id,
            enterprise_customer=enterprise_customer,
        )
        client = course_api_client_mock.return_value
        client.get_course_details.return_value = {
            'name': 'edX Demo Course',
        }
        reverse_mock.return_value = '/dashboard'
        resp = self.client.post(
            self.url,
            data={
                'course_id': course_id,
                'redirect_url': '/successful_enrollment'
            },
        )
        assert resp.status_code == 302
        self.assertRedirects(
            resp,
            '/accounts/login/?next=/enterprise/grant_data_sharing_permissions',
            fetch_redirect_response=False
        )

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.CourseApiClient')
    @mock.patch('enterprise.views.reverse')
    def test_post_course_specific_consent_bad_api_response(
            self,
            reverse_mock,
            course_api_client_mock,
            *args
    ):  # pylint: disable=unused-argument
        self._login()
        course_id = 'course-v1:does+not+exist'
        data_sharing_consent = True
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        ecu = EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=enterprise_customer
        )
        EnterpriseCourseEnrollment.objects.create(
            enterprise_customer_user=ecu,
            course_id=course_id
        )
        dsc = DataSharingConsentFactory(
            username=self.user.username,
            course_id=course_id,
            enterprise_customer=enterprise_customer,
            granted=False,
        )
        client = course_api_client_mock.return_value
        client.get_course_details.return_value = None
        reverse_mock.return_value = '/dashboard'
        resp = self.client.post(
            self.url,
            data={
                'course_id': course_id,
                'data_sharing_consent': data_sharing_consent,
                'redirect_url': '/successful_enrollment'
            },
        )
        assert resp.status_code == 404
        dsc.refresh_from_db()
        assert dsc.granted is False


@mark.django_db
@ddt.ddt
class TestProgramDataSharingPermissions(TestCase):
    """
    Test the user-facing program consent view
    """

    url = reverse('grant_data_sharing_permissions')

    valid_get_params = {
        'enterprise_customer_uuid': 'fake-uuid',
        'next': 'https://google.com/',
        'failure_url': 'https://facebook.com/',
        'program_uuid': 'fake-program-uuid',
    }
    valid_post_params = {
        'enterprise_customer_uuid': 'fake-uuid',
        'redirect_url': 'https://google.com/',
        'failure_url': 'https://facebook.com/',
        'program_uuid': 'fake-program-uuid',
        'data_sharing_consent': 'true',
    }

    def setUp(self):
        self.user = UserFactory.create(username='john', is_staff=True, is_active=True)
        self.user.set_password("QWERTY")
        self.user.save()
        self.client = Client()
        get_dsc = mock.patch('enterprise.views.get_data_sharing_consent')
        self.get_data_sharing_consent = get_dsc.start()
        self.addCleanup(get_dsc.stop)
        course_catalog_api_client = mock.patch('enterprise.views.CourseCatalogApiServiceClient')
        self.course_catalog_api_client = course_catalog_api_client.start()
        self.addCleanup(course_catalog_api_client.stop)
        super(TestProgramDataSharingPermissions, self).setUp()

    def _login(self):
        """
        Log user in.
        """
        assert self.client.login(username=self.user.username, password="QWERTY")

    @ddt.data(
        'enterprise_customer_uuid',
        'next',
        'failure_url',
        'program_uuid',
    )
    def test_get_program_consent_missing_parameter(self, missing_parameter):
        self.course_catalog_api_client.return_value.program_exists.return_value = True
        valid_get_params = self.valid_get_params.copy()
        valid_get_params.pop(missing_parameter)
        self._login()
        response = self.client.get(self.url, valid_get_params)
        assert response.status_code == 404

    def test_get_consent_program_does_not_exist(self):
        self.course_catalog_api_client.return_value.program_exists.return_value = False
        self._login()
        response = self.client.get(self.url, self.valid_get_params)
        assert response.status_code == 404

    def test_get_program_consent_no_ec(self):
        self.get_data_sharing_consent.return_value = None
        self.course_catalog_api_client.return_value.program_exists.return_value = True
        self._login()
        response = self.client.get(self.url, self.valid_get_params)
        assert response.status_code == 404

    def test_get_program_consent_not_required(self):
        self.get_data_sharing_consent.return_value.consent_required.return_value = False
        self.course_catalog_api_client.return_value.program_exists.return_value = True
        self._login()
        response = self.client.get(self.url, self.valid_get_params)
        assert response.status_code == 404

    @ddt.data(
        'enterprise_customer_uuid',
        'redirect_url',
        'failure_url',
        'program_uuid',
    )
    def test_post_program_consent_missing_parameter(self, missing_parameter):
        self.course_catalog_api_client.return_value.program_exists.return_value = True
        valid_post_params = self.valid_post_params.copy()
        valid_post_params.pop(missing_parameter)
        self._login()
        response = self.client.post(self.url, valid_post_params)
        assert response.status_code == 404

    def test_post_consent_program_does_not_exist(self):
        self.course_catalog_api_client.return_value.program_exists.return_value = False
        self._login()
        response = self.client.post(self.url, self.valid_post_params)
        assert response.status_code == 404

    def test_post_program_consent_no_ec(self):
        self.get_data_sharing_consent.return_value = None
        self.course_catalog_api_client.return_value.program_exists.return_value = True
        self._login()
        response = self.client.post(self.url, self.valid_post_params)
        assert response.status_code == 404

    def test_post_program_consent_not_required(self):
        self.get_data_sharing_consent.return_value.consent_required.return_value = False
        self.course_catalog_api_client.return_value.program_exists.return_value = True
        self._login()
        response = self.client.get(self.url, self.valid_post_params)
        assert response.status_code == 404

    def test_post_program_consent(self):
        consent_record = self.get_data_sharing_consent.return_value
        consent_record.consent_required.return_value = True
        self.course_catalog_api_client.return_value.program_exists.return_value = True
        self._login()
        response = self.client.post(self.url, self.valid_post_params, follow=False)
        consent_record.save.assert_called_once()
        self.assertRedirects(response, 'https://google.com/', fetch_redirect_response=False)

    def test_post_program_consent_not_provided(self):
        consent_record = self.get_data_sharing_consent.return_value
        consent_record.consent_required.return_value = True
        self.course_catalog_api_client.return_value.program_exists.return_value = True
        self._login()
        params = self.valid_post_params.copy()
        params.pop('data_sharing_consent')
        response = self.client.post(self.url, params, follow=False)
        consent_record.save.assert_called_once()
        self.assertRedirects(response, 'https://facebook.com/', fetch_redirect_response=False)

    def test_post_program_consent_deferred(self):
        consent_record = self.get_data_sharing_consent.return_value
        consent_record.consent_required.return_value = True
        self.course_catalog_api_client.return_value.program_exists.return_value = True
        self._login()
        params = self.valid_post_params.copy()
        params['defer_creation'] = 'True'
        response = self.client.post(self.url, params, follow=False)
        consent_record.save.assert_not_called()
        self.assertRedirects(response, 'https://google.com/', fetch_redirect_response=False)

    @ddt.data(False, True)
    @mock.patch('enterprise.views.render', side_effect=fake_render)
    def test_get_program_consent(self, defer_creation, mock_render):  # pylint: disable=unused-argument
        self.get_data_sharing_consent.return_value.consent_required.return_value = True
        enterprise_customer = self.get_data_sharing_consent.return_value.enterprise_customer
        enterprise_customer.name = 'Starfleet Academy'
        self.course_catalog_api_client.return_value.program_exists.return_value = True
        self._login()
        params = self.valid_get_params.copy()
        if defer_creation:
            params.update({'defer_creation': True})
        response = self.client.get(self.url, params)
        assert response.status_code == 200

        expected_prompt = (
            'To access this program, you must first consent to share your learning achievements '
            'with <b>Starfleet Academy</b>.'
        )
        expected_alert = (
            'In order to start this program and use your discount, <b>you must</b> consent to share your '
            'program data with Starfleet Academy.'
        )

        for key, value in {
                "platform_name": "Test platform",
                "platform_description": "Test description",
                "consent_request_prompt": expected_prompt,
                "requested_permissions_header": (
                    'Per the <a href="#consent-policy-dropdown-bar" '
                    'class="policy-dropdown-link background-input failure-link" id="policy-dropdown-link">'
                    'Data Sharing Policy</a>, <b>Starfleet Academy</b> would like to know about:'
                ),
                'confirmation_alert_prompt': expected_alert,
                'confirmation_alert_prompt_warning': '',
                'sharable_items_footer': (
                    'My permission applies only to data from courses or programs that are sponsored by '
                    'Starfleet Academy, and not to data from any Test platform courses or programs that '
                    'I take on my own. I understand that once I grant my permission to allow data to be shared '
                    'with Starfleet Academy, I may not withdraw my permission but I may elect to unenroll '
                    'from any courses that are sponsored by Starfleet Academy.'
                ),
                "program_uuid": params.get('program_uuid'),
                "redirect_url": "https://google.com/",
                "failure_url": "https://facebook.com/",
                "program_specific": True,
                "defer_creation": defer_creation,
                "welcome_text": "Welcome to Test platform.",
                'sharable_items_note_header': 'Please note',
                "enterprise_customer": enterprise_customer,
                'LMS_SEGMENT_KEY': settings.LMS_SEGMENT_KEY,
        }.items():
            assert response.context[key] == value  # pylint:disable=no-member
