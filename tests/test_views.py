"""
Module tests user-facing views of the Enterprise app.
"""
from __future__ import absolute_import, unicode_literals

import inspect

import ddt
import mock
from dateutil.parser import parse
from faker import Factory as FakerFactory
from pytest import mark, raises

from django.contrib import messages
from django.core.urlresolvers import NoReverseMatch, reverse
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.test import Client, TestCase

from enterprise.models import EnterpriseCourseEnrollment, EnterpriseCustomerUser, UserDataSharingConsentAudit
from enterprise.utils import NotConnectedToOpenEdX
from enterprise.views import (
    CONFIRMATION_ALERT_PROMPT,
    CONFIRMATION_ALERT_PROMPT_WARNING,
    CONSENT_REQUEST_PROMPT,
    LMS_COURSEWARE_URL,
    LMS_DASHBOARD_URL,
    LMS_START_PREMIUM_COURSE_FLOW_URL,
    GrantDataSharingPermissions,
    HttpClientError,
)

# pylint: disable=import-error,wrong-import-order
from six.moves.urllib.parse import urlencode

from test_utils.factories import (
    EnterpriseCustomerFactory,
    EnterpriseCustomerIdentityProviderFactory,
    EnterpriseCustomerUserFactory,
    UserFactory,
)


def fake_render(request, template, context):  # pylint: disable=unused-argument
    """
    Switch the request to use a template that does not depend on edx-platform.
    """
    return render(request, 'enterprise/emails/user_notification.html', context=context)


@mark.django_db
@ddt.ddt
class TestGrantDataSharingPermissions(TestCase):
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

    def _assert_request_message(self, request_message, expected_message_tags, expected_message_text):
        """
        Verify the request message tags and text.
        """
        self.assertEqual(request_message.tags, expected_message_tags)
        self.assertEqual(request_message.message, expected_message_text)

    def _assert_enterprise_linking_messages(self, response, user_is_active=True):
        """
        Verify response messages for a learner when he/she is linked with an
        enterprise depending on whether the learner has activated the linked
        account.
        """
        # pylint: disable=protected-access
        response_messages = messages.storage.cookie.CookieStorage(response)._decode(response.cookies['messages'].value)
        if user_is_active:
            # Verify that request contains the expected success message when a
            # learner with activated account is linked with an enterprise
            self.assertEqual(len(response_messages), 1)
            self._assert_request_message(
                response_messages[0],
                'success',
                '<span>Account created</span> Thank you for creating an account with edX.'
            )
        else:
            # Verify that request contains the expected success message and an
            # info message when a learner with unactivated account is linked
            # with an enterprise.
            self.assertEqual(len(response_messages), 2)
            self._assert_request_message(
                response_messages[0],
                'success',
                '<span>Account created</span> Thank you for creating an account with edX.'
            )
            self._assert_request_message(
                response_messages[1],
                'info',
                '<span>Activate your account</span> Check your inbox for an activation email. '
                'You will not be able to log back into your account until you have activated it.'
            )

    @mock.patch('enterprise.views.quarantine_session')
    def test_quarantine(self, mock_quarantine):
        """
        Check that ``quarantine`` adds the appropriate items to the session.
        """
        request = mock.MagicMock()
        GrantDataSharingPermissions.quarantine(request)
        mock_quarantine.assert_called_with(request, ('enterprise.views',))

    @mock.patch('enterprise.views.lift_quarantine')
    def test_lift_quarantine(self, mock_lift):
        """
        Check that ``lift_quarantine`` removes the appropriate items.
        """
        request = mock.MagicMock()
        GrantDataSharingPermissions.lift_quarantine(request)
        mock_lift.assert_called_with(request)

    def test_get_no_patches(self):
        """
        Test that we get the right exception when nothing is patched.
        """
        client = Client()
        with raises(NotConnectedToOpenEdX) as excinfo:
            client.get(self.url)
        self.assertIsNotNone(excinfo.value)

    @mock.patch('enterprise.views.get_partial_pipeline')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.get_complete_url')
    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.redirect')
    @mock.patch('enterprise.views.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.configuration_helpers')
    def test_get_no_customer_redirect(
            self,
            config_mock,
            get_ec_mock,
            redirect_mock,
            *args
    ):  # pylint: disable=unused-argument
        """
        Test that view redirects to login screen if it can't get an EnterpriseCustomer from the pipeline.

        Note that this test needs to patch `django.shortcuts.redirect`.
        This is because the target view ('signin_user') only exists in edx-platform.
        """
        config_mock.get_value.return_value = 'This Platform'
        get_ec_mock.return_value = None
        redirect_url = '/fake/path'
        mock_response = HttpResponseRedirect(redirect_url)
        redirect_mock.return_value = mock_response
        client = Client()
        response = client.get(self.url)
        self.assertRedirects(response, redirect_url, fetch_redirect_response=False)
        redirect_mock.assert_called_once_with('signin_user')

    @ddt.data(True, False)
    @mock.patch('enterprise.views.get_partial_pipeline')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.get_complete_url')
    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.configuration_helpers')
    def test_get_render_patched(
            self,
            enforces_data_sharing_consent,
            config_mock,
            get_ec_mock,
            *args
    ):  # pylint: disable=unused-argument
        """
        Test that we have the appropriate context when rendering the form,
        for both mandatory and optional data sharing consent.
        """
        config_mock.get_value.return_value = 'This Platform'
        fake_ec = mock.MagicMock(
            enforces_data_sharing_consent=mock.MagicMock(return_value=enforces_data_sharing_consent)
        )
        fake_ec.name = 'Fake Customer Name'
        get_ec_mock.return_value = fake_ec
        client = Client()
        response = client.get(self.url)
        expected_prompt = CONSENT_REQUEST_PROMPT.format(  # pylint: disable=no-member
            enterprise_customer_name=fake_ec.name
        )
        expected_alert = CONFIRMATION_ALERT_PROMPT.format(  # pylint: disable=no-member
            enterprise_customer_name=fake_ec.name
        )
        expected_warning = CONFIRMATION_ALERT_PROMPT_WARNING.format(  # pylint: disable=no-member
            enterprise_customer_name=fake_ec.name
        )
        expected_context = {
            'consent_request_prompt': expected_prompt,
            'confirmation_alert_prompt': expected_alert,
            'confirmation_alert_prompt_warning': expected_warning,
            'platform_name': 'This Platform',
            'enterprise_customer_name': 'Fake Customer Name',
        }
        for key, value in expected_context.items():
            assert response.context[key] == value  # pylint: disable=no-member

    @mock.patch('enterprise.views.get_partial_pipeline')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.get_complete_url')
    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.configuration_helpers')
    def test_get_render_patched_optional(
            self,
            config_mock,
            get_ec_mock,
            *args
    ):  # pylint: disable=unused-argument
        """
        Test that we have correct context for an optional form rendering.
        """
        config_mock.get_value.return_value = 'This Platform'
        fake_ec = mock.MagicMock(
            enforces_data_sharing_consent=mock.MagicMock(return_value=False)
        )
        fake_ec.name = 'Fake Customer Name'
        get_ec_mock.return_value = fake_ec
        client = Client()
        response = client.get(self.url)
        expected_prompt = CONSENT_REQUEST_PROMPT.format(  # pylint: disable=no-member
            enterprise_customer_name=fake_ec.name
        )
        expected_alert = CONFIRMATION_ALERT_PROMPT.format(  # pylint: disable=no-member
            enterprise_customer_name=fake_ec.name
        )
        expected_warning = CONFIRMATION_ALERT_PROMPT_WARNING.format(  # pylint: disable=no-member
            enterprise_customer_name=fake_ec.name
        )
        expected_context = {
            'consent_request_prompt': expected_prompt,
            'confirmation_alert_prompt': expected_alert,
            'confirmation_alert_prompt_warning': expected_warning,
            'platform_name': 'This Platform',
            'enterprise_customer_name': 'Fake Customer Name',
        }
        for key, value in expected_context.items():
            assert response.context[key] == value  # pylint: disable=no-member

    @mock.patch('enterprise.views.get_partial_pipeline')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.render')
    @mock.patch('enterprise.views.get_complete_url')
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.redirect')
    @mock.patch('enterprise.views.get_enterprise_customer_for_request')
    def test_post_no_customer_redirect(
            self,
            mock_get_ec,
            mock_redirect,
            *args
    ):  # pylint: disable=unused-argument
        """
        Test that when there's no customer for the request, POST redirects to the login screen.

        Note that this test needs to patch `django.shortcuts.redirect`.
        This is because the target view ('signin_user') only exists in edx-platform.
        """
        mock_get_ec.return_value = None
        redirect_url = '/fake/path'
        mock_response = HttpResponseRedirect(redirect_url)
        mock_redirect.return_value = mock_response
        client = Client()
        response = client.post(self.url)
        self.assertRedirects(response, redirect_url, fetch_redirect_response=False)
        mock_redirect.assert_called_once_with('signin_user')

    @mock.patch('enterprise.views.get_partial_pipeline')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.render')
    @mock.patch('enterprise.views.get_complete_url')
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.get_enterprise_customer_for_request')
    def test_post_no_user_404(
            self,
            mock_get_ec,
            mock_get_rsa,
            *args
    ):  # pylint: disable=unused-argument
        """
        Test that when there's no customer for the request, POST gives a 404.
        """
        mock_get_ec.return_value = True
        mock_get_rsa.return_value = None
        client = Client()
        response = client.post(self.url)
        assert response.status_code == 404

    @mock.patch('enterprise.views.get_partial_pipeline')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.render')
    @mock.patch('enterprise.views.get_complete_url')
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.get_enterprise_customer_for_request')
    def test_post_patch_real_social_auth_enforced(
            self,
            mock_get_ec,
            mock_get_rsa,
            mock_get_ec2,
            *args
    ):  # pylint: disable=unused-argument
        """
        Test an enforecd request without consent.
        """
        customer = EnterpriseCustomerFactory()
        mock_get_ec.return_value = customer
        mock_get_ec2.return_value = customer
        mock_get_rsa.return_value = mock.MagicMock(user=UserFactory())
        with raises(NoReverseMatch) as excinfo:
            client = Client()
            session = client.session
            session['partial_pipeline_token'] = True
            session.save()
            client.post(self.url)
        expected = (
            'Reverse for \'dashboard\' with arguments \'()\' and keyword '
            'arguments \'{}\' not found. 0 pattern(s) tried: []'
        )
        assert str(excinfo.value) == expected
        # Ensure that when consent hasn't been provided, we don't link the user to the Enterprise Customer.
        assert UserDataSharingConsentAudit.objects.all().count() == 0
        assert EnterpriseCustomerUser.objects.all().count() == 0

    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.render')
    @mock.patch('enterprise.views.get_partial_pipeline')
    @mock.patch('enterprise.views.get_complete_url')
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.get_enterprise_customer_for_request')
    def test_permission_not_required(
            self,
            mock_get_ec,
            mock_get_rsa,
            mock_get_ec2,
            mock_url,
            mock_partial,
            *args
    ):  # pylint: disable=unused-argument
        """
        Test an unenforced request
        """
        customer = EnterpriseCustomerFactory(enable_data_sharing_consent=False)
        mock_get_ec.return_value = customer
        mock_get_ec2.return_value = customer
        mock_get_rsa.return_value = mock.MagicMock(user=UserFactory())
        mock_url.return_value = '/'
        mock_partial.return_value = {'backend': 'fake_backend'}
        client = Client()
        response = client.post(self.url)
        assert UserDataSharingConsentAudit.objects.all().count() == 1
        assert EnterpriseCustomerUser.objects.all().count() == 1
        assert not UserDataSharingConsentAudit.objects.all()[0].enabled
        assert response.status_code == 302

    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.render')
    @mock.patch('enterprise.views.get_partial_pipeline')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.get_complete_url')
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.get_enterprise_customer_for_request')
    @ddt.data(False, True)
    def test_post_patch_real_social_auth_enabled(
            self,
            user_is_active,
            mock_get_ec,
            mock_get_rsa,
            mock_get_ec2,
            mock_url,
            mock_config,
            mock_partial,
            *args
    ):  # pylint: disable=unused-argument
        """
        Test an enforced request with consent and rendering patched in.
        """
        mock_config.get_value.return_value = 'edX'
        customer = EnterpriseCustomerFactory()
        mock_get_ec.return_value = customer
        mock_get_ec2.return_value = customer
        mock_get_rsa.return_value = mock.MagicMock(user=UserFactory(is_active=user_is_active))
        mock_url.return_value = '/'
        client = Client()
        mock_partial.return_value = {'backend': 'fake_backend'}
        response = client.post(self.url, {'data_sharing_consent': True})
        assert UserDataSharingConsentAudit.objects.all().count() == 1
        assert EnterpriseCustomerUser.objects.all().count() == 1
        assert UserDataSharingConsentAudit.objects.all()[0].enabled
        assert response.status_code == 302

        # Now verify that response contains the expected messages when a
        # learner is linked with an enterprise
        self._assert_enterprise_linking_messages(response, user_is_active)

    @mock.patch('enterprise.views.get_partial_pipeline')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.render')
    @mock.patch('enterprise.views.get_complete_url')
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.get_enterprise_customer_for_request')
    def test_post_patch_real_social_auth_no_consent_provided(
            self,
            mock_get_ec,
            mock_get_rsa,
            mock_get_ec2,
            mock_url,
            *args
    ):  # pylint: disable=unused-argument
        """
        Test an enforced request with consent and rendering patched in.
        """
        customer = EnterpriseCustomerFactory()
        mock_get_ec.return_value = customer
        mock_get_ec2.return_value = customer
        mock_get_rsa.return_value = mock.MagicMock(user=UserFactory())
        mock_url.return_value = '/'
        client = Client()
        session = client.session
        session['partial_pipeline_token'] = {'backend': 'fake_backend'}
        session.save()
        response = client.post(self.url, {'failure_url': 'http://google.com/'})
        assert UserDataSharingConsentAudit.objects.all().count() == 0
        assert EnterpriseCustomerUser.objects.all().count() == 0
        assert response.status_code == 302

    def _login(self):
        """
        Log user in.
        """
        assert self.client.login(username=self.user.username, password="QWERTY")

    @mock.patch('enterprise.views.get_partial_pipeline')
    @mock.patch('enterprise.views.get_complete_url')
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.CourseApiClient')
    @ddt.data(
        (False, False),
        (True, True),
    )
    @ddt.unpack
    def test_get_course_specific_consent(
            self,
            enrollment_deferred,
            supply_customer_uuid,
            course_api_client_mock,
            mock_config,
            *args
    ):  # pylint: disable=unused-argument
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        mock_config.get_value.return_value = 'My Platform'
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
        params = {
            'course_id': 'course-v1:edX+DemoX+Demo_Course',
            'next': 'https://google.com'
        }
        if enrollment_deferred:
            params['enrollment_deferred'] = True
        if supply_customer_uuid:
            params['enterprise_id'] = str(enterprise_customer.uuid)
        response = self.client.get(self.url, data=params)
        assert response.status_code == 200
        expected_prompt = (
            'To access this course and use your discount, you must first consent to share your '
            'learning achievements with <b>Starfleet Academy</b>.'
        )
        expected_alert = (
            'In order to start this course and use your discount, <b>you must</b> consent to share your '
            'course data with Starfleet Academy.'
        )
        expected_warning = CONFIRMATION_ALERT_PROMPT_WARNING.format(  # pylint: disable=no-member
            enterprise_customer_name='Starfleet Academy'
        )
        for key, value in {
                "platform_name": "My Platform",
                "consent_request_prompt": expected_prompt,
                'confirmation_alert_prompt': expected_alert,
                'confirmation_alert_prompt_warning': expected_warning,
                'sharable_items_footer': (
                    'My permission applies only to data from courses or programs that are sponsored by '
                    'Starfleet Academy, and not to data from any My Platform courses or programs that '
                    'I take on my own. I understand that once I grant my permission to allow data to be shared '
                    'with Starfleet Academy, I may not withdraw my permission but I may elect to unenroll '
                    'from any courses or programs that are sponsored by Starfleet Academy.'
                ),
                "course_id": "course-v1:edX+DemoX+Demo_Course",
                "course_name": "edX Demo Course",
                "redirect_url": "https://google.com",
                "enterprise_customer_name": ecu.enterprise_customer.name,
                "course_specific": True,
                "enrollment_deferred": enrollment_deferred,
        }.items():
            assert response.context[key] == value  # pylint:disable=no-member

    @mock.patch('enterprise.views.get_partial_pipeline')
    @mock.patch('enterprise.views.get_complete_url')
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.CourseApiClient')
    @ddt.data(
        (False, False),
        (True, True),
    )
    @ddt.unpack
    def test_get_course_specific_consent_ec_requires_account_level(
            self,
            enrollment_deferred,
            supply_customer_uuid,
            course_api_client_mock,
            mock_config,
            *args
    ):  # pylint: disable=unused-argument
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        mock_config.get_value.return_value = 'My Platform'
        client = course_api_client_mock.return_value
        client.get_course_details.return_value = {
            'name': 'edX Demo Course',
        }
        self._login()
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
            require_account_level_consent=True,
        )
        ecu = EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=enterprise_customer
        )
        EnterpriseCourseEnrollment.objects.create(
            enterprise_customer_user=ecu,
            course_id=course_id
        )
        params = {
            'course_id': 'course-v1:edX+DemoX+Demo_Course',
            'next': 'https://google.com'
        }
        if enrollment_deferred:
            params['enrollment_deferred'] = True
        if supply_customer_uuid:
            params['enterprise_id'] = str(enterprise_customer.uuid)
        response = self.client.get(self.url, data=params)
        assert response.status_code == 200
        expected_prompt = (
            'To access this and other courses sponsored by <b>Starfleet Academy</b>, and to '
            'use the discounts available to you, you must first consent to share your '
            'learning achievements with <b>Starfleet Academy</b>.'
        )
        expected_alert = (
            'In order to start this course and use your discount, <b>you must</b> consent to share your '
            'course data with Starfleet Academy.'
        )
        expected_warning = CONFIRMATION_ALERT_PROMPT_WARNING.format(  # pylint: disable=no-member
            enterprise_customer_name='Starfleet Academy'
        )
        for key, value in {
                "platform_name": "My Platform",
                "consent_request_prompt": expected_prompt,
                'confirmation_alert_prompt': expected_alert,
                'confirmation_alert_prompt_warning': expected_warning,
                'sharable_items_footer': (
                    'My permission applies only to data from courses or programs that are sponsored by '
                    'Starfleet Academy, and not to data from any My Platform courses or programs that '
                    'I take on my own. I understand that once I grant my permission to allow data to be shared '
                    'with Starfleet Academy, I may not withdraw my permission but I may elect to unenroll '
                    'from any courses or programs that are sponsored by Starfleet Academy.'
                ),
                "course_id": "course-v1:edX+DemoX+Demo_Course",
                "course_name": "edX Demo Course",
                "redirect_url": "https://google.com",
                "enterprise_customer_name": ecu.enterprise_customer.name,
                "course_specific": True,
                "enrollment_deferred": enrollment_deferred,
        }.items():
            assert response.context[key] == value  # pylint:disable=no-member

    @mock.patch('enterprise.views.get_partial_pipeline')
    @mock.patch('enterprise.views.get_complete_url')
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.CourseApiClient')
    def test_get_course_specific_consent_invalid_params(
            self,
            course_api_client_mock,
            mock_config,
            *args
    ):  # pylint: disable=unused-argument
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        mock_config.get_value.return_value = 'My Platform'
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
        params = {
            'course_id': 'course-v1:edX+DemoX+Demo_Course',
            'next': 'https://google.com',
            'enrollment_deferred': True,
        }
        response = self.client.get(self.url, data=params)
        assert response.status_code == 404

    @mock.patch('enterprise.views.get_partial_pipeline')
    @mock.patch('enterprise.views.get_complete_url')
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.CourseApiClient')
    def test_get_course_specific_consent_unauthenticated_user(
            self,
            course_api_client_mock,
            mock_config,
            *args
    ):  # pylint: disable=unused-argument
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        mock_config.get_value.return_value = 'My Platform'
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

    @mock.patch('enterprise.views.get_partial_pipeline')
    @mock.patch('enterprise.views.get_complete_url')
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.CourseApiClient')
    def test_get_course_specific_consent_bad_api_response(
            self,
            course_api_client_mock,
            mock_config,
            *args
    ):  # pylint: disable=unused-argument
        self._login()
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        mock_config.get_value.return_value = 'My Platform'
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        client = course_api_client_mock.return_value
        client.get_course_details.side_effect = HttpClientError
        ecu = EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=enterprise_customer
        )
        EnterpriseCourseEnrollment.objects.create(
            enterprise_customer_user=ecu,
            course_id=course_id
        )
        response = self.client.get(
            self.url + '?course_id=course-v1%3AedX%2BDemoX%2BDemo_Course&next=https%3A%2F%2Fgoogle.com'
        )
        assert response.status_code == 404

    @mock.patch('enterprise.views.get_partial_pipeline')
    @mock.patch('enterprise.views.get_complete_url')
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.CourseApiClient')
    def test_get_course_specific_consent_not_needed(
            self,
            course_api_client_mock,
            mock_config,
            *args
    ):  # pylint: disable=unused-argument
        self._login()
        course_id = 'course-v1:edX+DemoX+Demo_Course'
        mock_config.get_value.return_value = 'My Platform'
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
            consent_granted=True,
        )
        response = self.client.get(
            self.url + '?course_id=course-v1%3AedX%2BDemoX%2BDemo_Course&next=https%3A%2F%2Fgoogle.com'
        )
        assert response.status_code == 404

    @mock.patch('enterprise.views.get_partial_pipeline')
    @mock.patch('enterprise.views.get_complete_url')
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.CourseApiClient')
    @mock.patch('enterprise.views.reverse')
    @ddt.data(True, False)
    def test_post_course_specific_consent(
            self,
            enrollment_deferred,
            reverse_mock,
            course_api_client_mock,
            *args
    ):  # pylint: disable=unused-argument
        self._login()
        course_id = 'course-v1:edX+DemoX+Demo_Course'
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
        enrollment = EnterpriseCourseEnrollment.objects.create(
            enterprise_customer_user=ecu,
            course_id=course_id
        )
        client = course_api_client_mock.return_value
        client.get_course_details.return_value = {
            'name': 'edX Demo Course',
        }
        reverse_mock.return_value = '/dashboard'
        post_data = {
            'course_id': course_id,
            'data_sharing_consent': data_sharing_consent,
            'redirect_url': '/successful_enrollment',
        }
        if enrollment_deferred:
            post_data['enrollment_deferred'] = True
        resp = self.client.post(self.url, post_data)
        assert resp.url.endswith('/successful_enrollment')  # pylint: disable=no-member
        assert resp.status_code == 302
        enrollment.refresh_from_db()
        assert enrollment.consent_granted is not enrollment_deferred

    @mock.patch('enterprise.views.get_partial_pipeline')
    @mock.patch('enterprise.views.get_complete_url')
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.CourseApiClient')
    @mock.patch('enterprise.views.reverse')
    def test_post_course_specific_consent_not_provided(
            self,
            reverse_mock,
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
        ecu = EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=enterprise_customer
        )
        enrollment = EnterpriseCourseEnrollment.objects.create(
            enterprise_customer_user=ecu,
            course_id=course_id
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
        assert resp.url.endswith('/dashboard')  # pylint: disable=no-member
        assert resp.status_code == 302
        enrollment.refresh_from_db()
        assert enrollment.consent_granted is False

    @mock.patch('enterprise.views.get_partial_pipeline')
    @mock.patch('enterprise.views.get_complete_url')
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.configuration_helpers')
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

    @mock.patch('enterprise.views.get_partial_pipeline')
    @mock.patch('enterprise.views.get_complete_url')
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.configuration_helpers')
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
        enrollment = EnterpriseCourseEnrollment.objects.create(
            enterprise_customer_user=ecu,
            course_id=course_id
        )
        client = course_api_client_mock.return_value
        client.get_course_details.side_effect = HttpClientError
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
        enrollment.refresh_from_db()
        assert enrollment.consent_granted is None


class TestPushLearnerDataToIntegratedChannel(TestCase):
    """
    Test PushLearnerDataToIntegratedChannel.
    """

    url = reverse('push_learner_data')

    def test_post(self):
        client = Client()
        try:
            client.post(self.url)
            self.fail("Should have raised NotImplementedError")
        except NotImplementedError:
            pass


class TestPushCatalogDataToIntegratedChannel(TestCase):
    """
    Test PushCatalogDataToIntegratedChannel.
    """

    url = reverse('push_catalog_data')

    def test_post(self):
        client = Client()
        try:
            client.post(self.url)
            self.fail("Should have raised NotImplementedError")
        except NotImplementedError:
            pass


@mark.django_db
@ddt.ddt
class TestCourseEnrollmentView(TestCase):
    """
    Test CourseEnrollmentView.
    """

    def setUp(self):
        self.user = UserFactory.create(is_staff=True, is_active=True)
        self.user.set_password("QWERTY")
        self.user.save()
        self.client = Client()
        self.demo_course_id = 'course-v1:edX+DemoX+Demo_Course'
        self.dummy_demo_course_details_data = {
            'name': 'edX Demo Course',
            'id': self.demo_course_id,
            'course_id': self.demo_course_id,
            'start': '2015-01-01T00:00:00Z',
            'start_display': 'Jan. 1, 2015',
            'end': None,
            'media': {
                'image': {
                    'small': 'http://localhost:8000/asset-v1:edX+DemoX+Demo_Course+type@asset+block@11-132x-blog.jpg',
                    'raw': 'http://localhost:8000/asset-v1:edX+DemoX+Demo_Course+type@asset+block@11-132x-blog.jpg',
                    'large': 'http://localhost:8000/asset-v1:edX+DemoX+Demo_Course+type@asset+block@11-132x-blog.jpg'
                },
                'course_video': {
                    'uri': None
                },
                'course_image': {
                    'uri': '/asset-v1:edX+DemoX+Demo_Course+type@asset+block@11-132x-blog.jpg'
                },
            },
            'pacing': u'instructor',
            'short_description': u'',
            'org': u'edX',
            'effort': '06:00',
            'overview': None,
        }
        self.dummy_demo_course_modes = [
            {
                "slug": "professional",
                "name": "Professional Track",
                "min_price": 100,
                "sku": "sku-professional",
            },
            {
                "slug": "audit",
                "name": "Audit Track",
                "min_price": 0,
                "sku": "sku-audit",
            },
        ]
        super(TestCourseEnrollmentView, self).setUp()

    def _login(self):
        """
        Log user in.
        """
        assert self.client.login(username=self.user.username, password="QWERTY")

    def _setup_course_catalog_client(self, client_mock):
        """
        Sets up the Course Catalog API client
        """
        client = client_mock.return_value
        client.get_course_run.return_value = {
            'level_type': 'Type 1',
        }

    def _setup_organizations_client(self, client_mock):
        """
        Sets up the Organizations API client
        """
        logo_mock = mock.MagicMock()
        logo_mock.url = 'logo.png'
        data = {
            'logo': logo_mock,
            'name': 'Organization',
        }
        client_mock.get_organization.return_value = data

    def _setup_course_api_client(self, client_mock):
        """
        Sets up the Courses API client
        """
        client = client_mock.return_value
        client.get_course_details.return_value = self.dummy_demo_course_details_data

    def _setup_enrollment_client(self, client_mock):
        """
        Sets up the Enrollment API client
        """
        client = client_mock.return_value
        client.get_course_modes.return_value = self.dummy_demo_course_modes
        client.get_course_enrollment.return_value = None

    def _setup_ecommerce_client(self, client_mock, total=50):
        """
        Sets up the Ecommerce API client
        """
        dummy_price_details_mock = mock.MagicMock()
        dummy_price_details_mock.return_value = {
            'total_incl_tax': total,
        }
        price_details_mock = mock.MagicMock()
        method_name = 'baskets.calculate.get'
        attrs = {method_name: dummy_price_details_mock}
        price_details_mock.configure_mock(**attrs)
        client_mock.return_value = price_details_mock

    def _setup_registry_mock(self, registry_mock, provider_id):
        """
        Sets up the SSO Registry object
        """
        registry_mock.get.return_value.configure_mock(provider_id=provider_id, drop_existing_session=False)

    @mock.patch('enterprise.views.get_partial_pipeline')
    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.CourseApiClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.views.organizations_helpers')
    @mock.patch('enterprise.views.CourseCatalogApiClient')
    @mock.patch('enterprise.views.ecommerce_api_client')
    @mock.patch('enterprise.utils.Registry')
    def test_get_course_enrollment_page(
            self,
            registry_mock,
            ecommerce_api_client_mock,
            course_catalog_client_mock,
            organizations_helpers_mock,
            enrollment_api_client_mock,
            course_api_client_mock,
            configuration_helpers_mock,
            *args
    ):  # pylint: disable=unused-argument
        self._setup_course_catalog_client(course_catalog_client_mock)
        self._setup_organizations_client(organizations_helpers_mock)
        self._setup_ecommerce_client(ecommerce_api_client_mock, 100)
        course_id = self.demo_course_id
        configuration_helpers_mock.get_value.return_value = 'edX'
        self._setup_course_api_client(course_api_client_mock)
        self._setup_enrollment_client(enrollment_api_client_mock)
        self._login()
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        faker = FakerFactory.create()
        provider_id = faker.slug()
        self._setup_registry_mock(registry_mock, provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=provider_id, enterprise_customer=enterprise_customer)
        enterprise_landing_page_url = reverse(
            'enterprise_course_enrollment_page',
            args=[enterprise_customer.uuid, course_id],
        )
        response = self.client.get(enterprise_landing_page_url)
        assert response.status_code == 200
        course_modes = [
            {
                "mode": "professional",
                "title": "Professional Track",
                "original_price": "$100",
                "min_price": 100,
                "sku": "sku-professional",
                "final_price": "$100",
                "description": "Earn a verified certificate!",
                "premium": True,
            }
        ]
        expected_context = {
            'platform_name': 'edX',
            'page_title': 'Choose Your Track',
            'course_id': course_id,
            'course_name': self.dummy_demo_course_details_data['name'],
            'course_organization': self.dummy_demo_course_details_data['org'],
            'course_short_description': self.dummy_demo_course_details_data['short_description'],
            'course_pacing': 'Instructor-Paced',
            'course_start_date': parse(self.dummy_demo_course_details_data['start']).strftime('%B %d, %Y'),
            'course_image_uri': self.dummy_demo_course_details_data['media']['course_image']['uri'],
            'enterprise_customer': enterprise_customer,
            'enterprise_welcome_text': (
                "<strong>Starfleet Academy</strong> has partnered with <strong>edX</strong> to "
                "offer you high-quality learning opportunities from the world's best universities."
            ),
            'confirmation_text': 'Confirm your course',
            'starts_at_text': 'Starts',
            'view_course_details_text': 'View Course Details',
            'select_mode_text': 'Please select one:',
            'price_text': 'Price',
            'continue_link_text': 'Continue',
            'course_modes': course_modes,
            'course_effort': '6 hours per week, per course',
            'level_text': 'Level',
            'effort_text': 'Effort',
            'course_overview': None,
            'organization_logo': 'logo.png',
            'organization_name': 'Organization',
            'course_level_type': 'Type 1',
            'close_modal_button_text': 'Close',
            'premium_modes': course_modes,
        }
        for key, value in expected_context.items():
            assert response.context[key] == value  # pylint: disable=no-member

    @mock.patch('enterprise.views.get_partial_pipeline')
    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.CourseApiClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.views.organizations_helpers')
    @mock.patch('enterprise.views.CourseCatalogApiClient')
    @mock.patch('enterprise.views.ecommerce_api_client')
    @mock.patch('enterprise.utils.Registry')
    def test_get_course_specific_enrollment_view_audit_enabled(
            self,
            registry_mock,
            ecommerce_api_client_mock,
            course_catalog_client_mock,
            organizations_helpers_mock,
            enrollment_api_client_mock,
            course_api_client_mock,
            configuration_helpers_mock,
            *args
    ):  # pylint: disable=unused-argument
        self._setup_course_catalog_client(course_catalog_client_mock)
        self._setup_organizations_client(organizations_helpers_mock)
        self._setup_ecommerce_client(ecommerce_api_client_mock)
        course_id = self.demo_course_id
        configuration_helpers_mock.get_value.return_value = 'edX'
        self._setup_course_api_client(course_api_client_mock)
        self._setup_enrollment_client(enrollment_api_client_mock)
        self._login()
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
            enable_audit_enrollment=True,
        )
        faker = FakerFactory.create()
        provider_id = faker.slug()
        self._setup_registry_mock(registry_mock, provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=provider_id, enterprise_customer=enterprise_customer)
        enterprise_landing_page_url = reverse(
            'enterprise_course_enrollment_page',
            args=[enterprise_customer.uuid, course_id],
        )
        response = self.client.get(enterprise_landing_page_url)
        assert response.status_code == 200
        course_modes = [
            {
                'mode': 'professional',
                'title': 'Professional Track',
                'original_price': '$100',
                'min_price': 100,
                'sku': 'sku-professional',
                'final_price': '$50',
                'description': 'Earn a verified certificate!',
                'premium': True,
            },
            {
                'mode': 'audit',
                'title': 'Audit Track',
                'original_price': 'FREE',
                'min_price': 0,
                'sku': 'sku-audit',
                'final_price': 'FREE',
                'description': 'Not eligible for a certificate; does not count toward a MicroMasters',
                'premium': False,
            }
        ]
        expected_context = {
            'platform_name': 'edX',
            'page_title': 'Choose Your Track',
            'course_id': course_id,
            'course_name': self.dummy_demo_course_details_data['name'],
            'course_organization': self.dummy_demo_course_details_data['org'],
            'course_short_description': self.dummy_demo_course_details_data['short_description'],
            'course_pacing': 'Instructor-Paced',
            'course_start_date': parse(self.dummy_demo_course_details_data['start']).strftime('%B %d, %Y'),
            'course_image_uri': self.dummy_demo_course_details_data['media']['course_image']['uri'],
            'enterprise_customer': enterprise_customer,
            'enterprise_welcome_text': (
                "<strong>Starfleet Academy</strong> has partnered with <strong>edX</strong> to "
                "offer you high-quality learning opportunities from the world's best universities."
            ),
            'confirmation_text': 'Confirm your course',
            'starts_at_text': 'Starts',
            'view_course_details_text': 'View Course Details',
            'select_mode_text': 'Please select one:',
            'price_text': 'Price',
            'continue_link_text': 'Continue',
            'course_modes': course_modes,
        }
        for key, value in expected_context.items():
            assert response.context[key] == value  # pylint: disable=no-member

    @mock.patch('enterprise.views.get_partial_pipeline')
    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.CourseApiClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.views.organizations_helpers')
    @mock.patch('enterprise.views.CourseCatalogApiClient')
    @mock.patch('enterprise.views.ecommerce_api_client')
    @mock.patch('enterprise.utils.Registry')
    def test_get_course_enrollment_page_with_no_start_date(
            self,
            registry_mock,
            ecommerce_api_client_mock,
            course_catalog_client_mock,
            organizations_helpers_mock,
            enrollment_api_client_mock,
            course_api_client_mock,
            configuration_helpers_mock,
            *args
    ):  # pylint: disable=unused-argument
        """
        Verify that the context of the enterprise course enrollment page has
        empty course start date if course details has no start date.
        """
        self._setup_course_catalog_client(course_catalog_client_mock)
        self._setup_organizations_client(organizations_helpers_mock)
        self._setup_ecommerce_client(ecommerce_api_client_mock)
        course_id = self.demo_course_id
        configuration_helpers_mock.get_value.return_value = 'edX'
        dummy_demo_course_details_data = self.dummy_demo_course_details_data
        dummy_demo_course_details_data['start'] = ''
        course_client = course_api_client_mock.return_value
        course_client.get_course_details.return_value = dummy_demo_course_details_data
        self._setup_enrollment_client(enrollment_api_client_mock)
        self._login()
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        faker = FakerFactory.create()
        provider_id = faker.slug()
        self._setup_registry_mock(registry_mock, provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=provider_id, enterprise_customer=enterprise_customer)
        course_enrollment_page_url = reverse(
            'enterprise_course_enrollment_page',
            args=[enterprise_customer.uuid, course_id],
        )
        response = self.client.get(course_enrollment_page_url)
        assert response.status_code == 200
        expected_context = {
            'platform_name': 'edX',
            'page_title': 'Choose Your Track',
            'course_id': course_id,
            'course_start_date': '',
        }
        for key, value in expected_context.items():
            assert response.context[key] == value  # pylint: disable=no-member

    @mock.patch('enterprise.views.get_partial_pipeline')
    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.CourseApiClient')
    @mock.patch('enterprise.utils.Registry')
    def test_get_course_enrollment_page_for_non_existing_course(
            self,
            registry_mock,
            course_api_client_mock,
            configuration_helpers_mock,
            *args
    ):  # pylint: disable=unused-argument
        """
        Verify that user will see HTTP 404 (Not Found) in case of invalid
        or non existing course.
        """
        configuration_helpers_mock.get_value.return_value = 'edX'
        course_client = course_api_client_mock.return_value
        course_client.get_course_details.return_value = None
        self._login()
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        faker = FakerFactory.create()
        provider_id = faker.slug()
        self._setup_registry_mock(registry_mock, provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=provider_id, enterprise_customer=enterprise_customer)
        course_enrollment_page_url = reverse(
            'enterprise_course_enrollment_page',
            args=[enterprise_customer.uuid, self.demo_course_id],
        )
        response = self.client.get(course_enrollment_page_url)
        assert response.status_code == 404

    @mock.patch('enterprise.views.get_partial_pipeline')
    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.CourseApiClient')
    @mock.patch('enterprise.utils.Registry')
    def test_get_course_enrollment_page_for_error_in_getting_course(
            self,
            registry_mock,
            course_api_client_mock,
            configuration_helpers_mock,
            *args
    ):  # pylint: disable=unused-argument
        """
        Verify that user will see HTTP 404 (Not Found) in case of error while
        getting the course details from CourseApiClient.
        """
        configuration_helpers_mock.get_value.return_value = 'edX'
        course_client = course_api_client_mock.return_value
        course_client.get_course_details.side_effect = HttpClientError
        self._login()
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        faker = FakerFactory.create()
        provider_id = faker.slug()
        self._setup_registry_mock(registry_mock, provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=provider_id, enterprise_customer=enterprise_customer)
        course_enrollment_page_url = reverse(
            'enterprise_course_enrollment_page',
            args=[enterprise_customer.uuid, self.demo_course_id],
        )
        response = self.client.get(course_enrollment_page_url)
        assert response.status_code == 404

    @mock.patch('enterprise.views.get_partial_pipeline')
    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.CourseApiClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.utils.Registry')
    def test_get_course_specific_enrollment_view_with_course_mode_error(
            self,
            registry_mock,
            enrollment_api_client_mock,
            course_api_client_mock,
            configuration_helpers_mock,
            *args
    ):  # pylint: disable=unused-argument
        """
        Verify that user will see HTTP 404 (Not Found) in case of invalid
        enterprise customer uuid.
        """
        configuration_helpers_mock.get_value.return_value = 'edX'
        self._setup_course_api_client(course_api_client_mock)
        enrollment_client = enrollment_api_client_mock.return_value
        enrollment_client.get_course_modes.side_effect = HttpClientError

        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        faker = FakerFactory.create()
        provider_id = faker.slug()
        self._setup_registry_mock(registry_mock, provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=provider_id, enterprise_customer=enterprise_customer)
        self._login()
        course_enrollment_page_url = reverse(
            'enterprise_course_enrollment_page',
            args=[enterprise_customer.uuid, self.demo_course_id],
        )
        response = self.client.get(course_enrollment_page_url)
        assert response.status_code == 404

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.CourseApiClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    def test_get_course_specific_enrollment_view_for_invalid_ec_uuid(
            self,
            enrollment_api_client_mock,
            course_api_client_mock,
            configuration_helpers_mock,
            *args
    ):  # pylint: disable=unused-argument
        """
        Verify that user will see HTTP 404 (Not Found) in case of invalid
        enterprise customer uuid.
        """
        configuration_helpers_mock.get_value.return_value = 'edX'
        self._setup_course_api_client(course_api_client_mock)
        self._setup_enrollment_client(enrollment_api_client_mock)
        self._login()
        course_enrollment_page_url = reverse(
            'enterprise_course_enrollment_page',
            args=['some-fake-enterprise-customer-uuid', self.demo_course_id],
        )
        response = self.client.get(course_enrollment_page_url)
        assert response.status_code == 404

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.utils.Registry')
    def test_get_course_enrollment_page_for_inactive_user(
            self,
            registry_mock,
            lift_quarantine_mock,   # pylint: disable=unused-argument
            quarantine_session_mock,    # pylint: disable=unused-argument
            social_auth_object_mock,   # pylint: disable=unused-argument
            get_ec_for_request_mock,   # pylint: disable=unused-argument
            configuration_helpers_mock,
            *args
    ):  # pylint: disable=unused-argument
        """
        Verify that user is redirected to login screen to sign in with an
        enterprise-linked SSO.
        """
        course_id = self.demo_course_id
        configuration_helpers_mock.get_value.return_value = 'edX'

        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        faker = FakerFactory.create()
        provider_id = faker.slug()
        self._setup_registry_mock(registry_mock, provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=provider_id, enterprise_customer=enterprise_customer)
        enterprise_landing_page_url = reverse(
            'enterprise_course_enrollment_page',
            args=[enterprise_customer.uuid, course_id],
        )
        response = self.client.get(enterprise_landing_page_url)
        expected_redirect_url = (
            '/login?next=%2Fenterprise%2F{enterprise_customer_uuid}%2Fcourse%2Fcourse-v1'
            '%253AedX%252BDemoX%252BDemo_Course%2Fenroll%2F%3Ftpa_hint%3D{provider_id}'
            '%26session_cleared%3Dyes'.format(
                enterprise_customer_uuid=enterprise_customer.uuid,
                provider_id=provider_id,
            )
        )
        self.assertRedirects(response, expected_redirect_url, fetch_redirect_response=False)

    @mock.patch('enterprise.views.get_partial_pipeline')
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.CourseApiClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.utils.Registry')
    def test_get_course_landing_page_for_enrolled_user(
            self,
            registry_mock,
            enrollment_api_client_mock,
            course_api_client_mock,
            configuration_helpers_mock,
            *args
    ):  # pylint: disable=unused-argument
        """
        Verify that the user will be redirected to the course home page when
        the user is already enrolled.
        """
        course_id = self.demo_course_id
        configuration_helpers_mock.get_value.return_value = 'edX'
        self._setup_course_api_client(course_api_client_mock)
        enrollment_client = enrollment_api_client_mock.return_value
        enrollment_client.get_course_modes.return_value = self.dummy_demo_course_modes
        enrollment_client.get_course_enrollment.return_value = {"course_details": {"course_id": course_id}}
        self._login()
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        faker = FakerFactory.create()
        provider_id = faker.slug()
        self._setup_registry_mock(registry_mock, provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=provider_id, enterprise_customer=enterprise_customer)
        ecu = EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=enterprise_customer
        )
        EnterpriseCourseEnrollment.objects.create(
            enterprise_customer_user=ecu,
            course_id=course_id
        )
        enterprise_landing_page_url = reverse(
            'enterprise_course_enrollment_page',
            args=[enterprise_customer.uuid, course_id],
        )
        response = self.client.get(enterprise_landing_page_url)
        self.assertRedirects(
            response,
            'http://localhost:8000/courses/{course_id}/courseware'.format(course_id=course_id),
            fetch_redirect_response=False,
        )

    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.CourseApiClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.views.is_consent_required_for_user')
    @mock.patch('enterprise.utils.Registry')
    def test_post_course_specific_enrollment_view(
            self,
            registry_mock,
            is_consent_required_mock,  # pylint: disable=invalid-name
            enrollment_api_client_mock,
            course_api_client_mock,
            configuration_helpers_mock,
            *args
    ):  # pylint: disable=unused-argument
        course_id = self.demo_course_id
        is_consent_required_mock.return_value = False
        configuration_helpers_mock.get_value.return_value = 'edX'
        self._setup_course_api_client(course_api_client_mock)
        enrollment_client = enrollment_api_client_mock.return_value
        enrollment_client.get_course_modes.return_value = self.dummy_demo_course_modes
        enrollment_client.get_course_enrollment.return_value = None

        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
            enable_audit_enrollment=True,
        )
        faker = FakerFactory.create()
        provider_id = faker.slug()
        self._setup_registry_mock(registry_mock, provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=provider_id, enterprise_customer=enterprise_customer)
        self._login()
        course_enrollment_page_url = reverse(
            'enterprise_course_enrollment_page',
            args=[enterprise_customer.uuid, course_id],
        )
        response = self.client.post(course_enrollment_page_url, {'course_mode': 'audit'})

        assert response.status_code == 302
        self.assertRedirects(
            response,
            'http://localhost:8000/courses/course-v1:edX+DemoX+Demo_Course/courseware',
            fetch_redirect_response=False
        )
        enrollment_client.enroll_user_in_course.assert_called_once_with(self.user.username, course_id, 'audit')

    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.CourseApiClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.views.is_consent_required_for_user')
    @mock.patch('enterprise.utils.Registry')
    def test_post_course_specific_enrollment_view_consent_needed(
            self,
            registry_mock,
            is_consent_required_mock,  # pylint: disable=invalid-name
            enrollment_api_client_mock,
            course_api_client_mock,
            configuration_helpers_mock,
            *args
    ):  # pylint: disable=unused-argument
        course_id = self.demo_course_id
        is_consent_required_mock.return_value = True
        configuration_helpers_mock.get_value.return_value = 'edX'
        client = course_api_client_mock.return_value
        client.get_course_details.return_value = self.dummy_demo_course_details_data
        enrollment_client = enrollment_api_client_mock.return_value
        enrollment_client.get_course_modes.return_value = self.dummy_demo_course_modes
        enrollment_client.get_course_enrollment.return_value = None

        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
            enable_audit_enrollment=True,
        )
        faker = FakerFactory.create()
        provider_id = faker.slug()
        self._setup_registry_mock(registry_mock, provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=provider_id, enterprise_customer=enterprise_customer)
        enterprise_id = enterprise_customer.uuid
        self._login()
        course_enrollment_page_url = reverse(
            'enterprise_course_enrollment_page',
            args=[enterprise_id, course_id],
        )
        response = self.client.post(course_enrollment_page_url, {'course_mode': 'audit'})

        assert response.status_code == 302

        expected_url_format = '/enterprise/grant_data_sharing_permissions?{}'
        consent_enrollment_url = '/enterprise/handle_consent_enrollment/{}/course/{}/?{}'.format(
            enterprise_id, course_id, urlencode({'course_mode': 'audit'})
        )
        self.assertRedirects(
            response,
            expected_url_format.format(
                urlencode(
                    {
                        'next': consent_enrollment_url,
                        'enterprise_id': enterprise_id,
                        'course_id': course_id,
                        'enrollment_deferred': True,
                    }
                )
            ),
            fetch_redirect_response=False
        )

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.CourseApiClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.views.organizations_helpers')
    @mock.patch('enterprise.views.CourseCatalogApiClient')
    @mock.patch('enterprise.views.ecommerce_api_client')
    @mock.patch('enterprise.utils.Registry')
    def test_post_course_specific_enrollment_view_incompatible_mode(
            self,
            registry_mock,
            ecommerce_api_client_mock,
            course_catalog_client_mock,
            organizations_helpers_mock,
            enrollment_api_client_mock,
            course_api_client_mock,
            configuration_helpers_mock,
            *args
    ):  # pylint: disable=unused-argument
        self._setup_course_catalog_client(course_catalog_client_mock)
        self._setup_organizations_client(organizations_helpers_mock)
        self._setup_ecommerce_client(ecommerce_api_client_mock)
        course_id = self.demo_course_id
        configuration_helpers_mock.get_value.return_value = 'edX'
        self._setup_course_api_client(course_api_client_mock)
        self._setup_enrollment_client(enrollment_api_client_mock)

        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
            enable_audit_enrollment=True,
        )
        faker = FakerFactory.create()
        provider_id = faker.slug()
        self._setup_registry_mock(registry_mock, provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=provider_id, enterprise_customer=enterprise_customer)
        self._login()
        course_enrollment_page_url = reverse(
            'enterprise_course_enrollment_page',
            args=[enterprise_customer.uuid, course_id],
        )
        response = self.client.post(course_enrollment_page_url, {'course_mode': 'fakemode'})

        assert response.status_code == 200
        expected_context = {
            'platform_name': 'edX',
            'page_title': 'Choose Your Track',
            'course_id': course_id,
            'course_name': self.dummy_demo_course_details_data['name'],
            'course_organization': self.dummy_demo_course_details_data['org'],
            'course_short_description': self.dummy_demo_course_details_data['short_description'],
            'course_pacing': 'Instructor-Paced',
            'course_start_date': parse(self.dummy_demo_course_details_data['start']).strftime('%B %d, %Y'),
            'course_image_uri': self.dummy_demo_course_details_data['media']['course_image']['uri'],
            'enterprise_customer': enterprise_customer,
            'enterprise_welcome_text': (
                "<strong>Starfleet Academy</strong> has partnered with <strong>edX</strong> to "
                "offer you high-quality learning opportunities from the world's best universities."
            ),
            'confirmation_text': 'Confirm your course',
            'starts_at_text': 'Starts',
            'view_course_details_text': 'View Course Details',
            'select_mode_text': 'Please select one:',
            'price_text': 'Price',
            'continue_link_text': 'Continue',
            'course_modes': [
                {
                    'mode': 'professional',
                    'title': 'Professional Track',
                    'original_price': '$100',
                    'min_price': 100,
                    'sku': 'sku-professional',
                    'final_price': '$50',
                    'description': 'Earn a verified certificate!',
                    'premium': True,
                },
                {
                    'mode': 'audit',
                    'title': 'Audit Track',
                    'original_price': 'FREE',
                    'min_price': 0,
                    'sku': 'sku-audit',
                    'final_price': 'FREE',
                    'description': 'Not eligible for a certificate; does not count toward a MicroMasters',
                    'premium': False,
                }
            ]
        }
        for key, value in expected_context.items():
            assert response.context[key] == value  # pylint: disable=no-member

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.CourseApiClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.views.is_consent_required_for_user')
    @mock.patch('enterprise.utils.Registry')
    def test_post_course_specific_enrollment_view_premium_mode(
            self,
            registry_mock,
            is_consent_required_mock,
            enrollment_api_client_mock,
            course_api_client_mock,
            configuration_helpers_mock,
            *args
    ):  # pylint: disable=unused-argument
        course_id = self.demo_course_id
        is_consent_required_mock.return_value = False
        configuration_helpers_mock.get_value.return_value = 'edX'
        self._setup_course_api_client(course_api_client_mock)
        self._setup_enrollment_client(enrollment_api_client_mock)
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
            enable_audit_enrollment=True,
        )
        faker = FakerFactory.create()
        provider_id = faker.slug()
        self._setup_registry_mock(registry_mock, provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=provider_id, enterprise_customer=enterprise_customer)
        self._login()
        course_enrollment_page_url = reverse(
            'enterprise_course_enrollment_page',
            args=[enterprise_customer.uuid, course_id],
        )
        response = self.client.post(course_enrollment_page_url, {'course_mode': 'professional'})

        assert response.status_code == 302
        self.assertRedirects(
            response,
            'http://localhost:8000/verify_student/start-flow/course-v1:edX+DemoX+Demo_Course/',
            fetch_redirect_response=False
        )

    @mock.patch('enterprise.views.get_partial_pipeline')
    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.CourseApiClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.views.organizations_helpers')
    @mock.patch('enterprise.views.CourseCatalogApiClient')
    @mock.patch('enterprise.views.ecommerce_api_client')
    @mock.patch('enterprise.utils.Registry')
    @ddt.data(None, 'Cannot convert to integer')
    def test_get_course_enrollment_page_with_unparseable_course_effort(
            self,
            course_effort,
            registry_mock,
            ecommerce_api_client_mock,
            course_catalog_client_mock,
            organizations_helpers_mock,
            enrollment_api_client_mock,
            course_api_client_mock,
            configuration_helpers_mock,
            *args
    ):  # pylint: disable=unused-argument
        # Set up Ecommerce API client
        self._setup_ecommerce_client(ecommerce_api_client_mock)
        # Set up course catalog API client
        self._setup_course_catalog_client(course_catalog_client_mock)

        # Set up organizations API client
        self._setup_organizations_client(organizations_helpers_mock)

        configuration_helpers_mock.get_value.return_value = 'edX'

        # Set up course API client
        dummy_demo_course_details_data = self.dummy_demo_course_details_data.copy()
        dummy_demo_course_details_data['effort'] = course_effort
        course_client = course_api_client_mock.return_value
        course_client.get_course_details.return_value = dummy_demo_course_details_data

        # Set up enrollment API client
        self._setup_enrollment_client(enrollment_api_client_mock)

        # Get landing page
        course_id = self.demo_course_id
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        faker = FakerFactory.create()
        provider_id = faker.slug()
        self._setup_registry_mock(registry_mock, provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=provider_id, enterprise_customer=enterprise_customer)
        enterprise_landing_page_url = reverse(
            'enterprise_course_enrollment_page',
            args=[enterprise_customer.uuid, course_id],
        )
        self._login()
        response = self.client.get(enterprise_landing_page_url)
        assert response.status_code == 200

        # Set up expected context
        course_modes = [
            {
                "mode": "professional",
                "title": "Professional Track",
                "original_price": "$100",
                "min_price": 100,
                "sku": "sku-professional",
                "final_price": "$50",
                "description": "Earn a verified certificate!",
                "premium": True,
            }
        ]
        expected_context = {
            'platform_name': 'edX',
            'page_title': 'Choose Your Track',
            'course_id': course_id,
            'course_name': self.dummy_demo_course_details_data['name'],
            'course_organization': self.dummy_demo_course_details_data['org'],
            'course_short_description': self.dummy_demo_course_details_data['short_description'],
            'course_pacing': 'Instructor-Paced',
            'course_start_date': parse(self.dummy_demo_course_details_data['start']).strftime('%B %d, %Y'),
            'course_image_uri': self.dummy_demo_course_details_data['media']['course_image']['uri'],
            'enterprise_customer': enterprise_customer,
            'enterprise_welcome_text': (
                "<strong>Starfleet Academy</strong> has partnered with <strong>edX</strong> to "
                "offer you high-quality learning opportunities from the world's best universities."
            ),
            'confirmation_text': 'Confirm your course',
            'starts_at_text': 'Starts',
            'view_course_details_text': 'View Course Details',
            'select_mode_text': 'Please select one:',
            'price_text': 'Price',
            'continue_link_text': 'Continue',
            'course_modes': course_modes,
            'course_effort': '',
            'level_text': 'Level',
            'effort_text': 'Effort',
            'course_overview': None,
            'organization_logo': 'logo.png',
            'organization_name': 'Organization',
            'course_level_type': 'Type 1',
            'close_modal_button_text': 'Close',
            'premium_modes': course_modes,
        }

        # Compare expected context with response result
        for key, value in expected_context.items():
            assert response.context[key] == value  # pylint: disable=no-member

    @mock.patch('enterprise.views.get_partial_pipeline')
    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.CourseApiClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.views.organizations_helpers')
    @mock.patch('enterprise.views.CourseCatalogApiClient')
    @mock.patch('enterprise.views.ecommerce_api_client')
    @mock.patch('enterprise.utils.Registry')
    @ddt.data(None, ValueError)
    def test_get_course_enrollment_page_organization_errors(
            self,
            organizations_data,
            registry_mock,
            ecommerce_api_client_mock,
            course_catalog_client_mock,
            organizations_helpers_mock,
            enrollment_api_client_mock,
            course_api_client_mock,
            configuration_helpers_mock,
            *args
    ):  # pylint: disable=unused-argument
        # Set up Ecommerce API client
        self._setup_ecommerce_client(ecommerce_api_client_mock)
        # Set up course catalog API client
        self._setup_course_catalog_client(course_catalog_client_mock)

        # Set up organizations API client
        if inspect.isclass(organizations_data) and issubclass(organizations_data, Exception):
            organizations_helpers_mock.get_organization.side_effect = organizations_data
        else:
            organizations_helpers_mock.get_organization.return_value = organizations_data

        configuration_helpers_mock.get_value.return_value = 'edX'

        # Set up course API client
        self._setup_course_api_client(course_api_client_mock)

        # Set up enrollment API client
        self._setup_enrollment_client(enrollment_api_client_mock)

        # Get landing page
        course_id = self.demo_course_id
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        faker = FakerFactory.create()
        provider_id = faker.slug()
        self._setup_registry_mock(registry_mock, provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=provider_id, enterprise_customer=enterprise_customer)
        enterprise_landing_page_url = reverse(
            'enterprise_course_enrollment_page',
            args=[enterprise_customer.uuid, course_id],
        )
        self._login()
        response = self.client.get(enterprise_landing_page_url)
        assert response.status_code == 200

        # Set up expected context
        course_modes = [
            {
                "mode": "professional",
                "title": "Professional Track",
                "original_price": "$100",
                "min_price": 100,
                "sku": "sku-professional",
                "final_price": "$50",
                "description": "Earn a verified certificate!",
                "premium": True,
            }
        ]
        expected_context = {
            'platform_name': 'edX',
            'page_title': 'Choose Your Track',
            'course_id': course_id,
            'course_name': self.dummy_demo_course_details_data['name'],
            'course_organization': self.dummy_demo_course_details_data['org'],
            'course_short_description': self.dummy_demo_course_details_data['short_description'],
            'course_pacing': 'Instructor-Paced',
            'course_start_date': parse(self.dummy_demo_course_details_data['start']).strftime('%B %d, %Y'),
            'course_image_uri': self.dummy_demo_course_details_data['media']['course_image']['uri'],
            'enterprise_customer': enterprise_customer,
            'enterprise_welcome_text': (
                "<strong>Starfleet Academy</strong> has partnered with <strong>edX</strong> to "
                "offer you high-quality learning opportunities from the world's best universities."
            ),
            'confirmation_text': 'Confirm your course',
            'starts_at_text': 'Starts',
            'view_course_details_text': 'View Course Details',
            'select_mode_text': 'Please select one:',
            'price_text': 'Price',
            'continue_link_text': 'Continue',
            'course_modes': course_modes,
            'course_effort': '6 hours per week, per course',
            'level_text': 'Level',
            'effort_text': 'Effort',
            'course_overview': None,
            'organization_logo': None,
            'organization_name': None,
            'course_level_type': 'Type 1',
            'close_modal_button_text': 'Close',
            'premium_modes': course_modes,
        }
        for key, value in expected_context.items():
            assert response.context[key] == value  # pylint: disable=no-member

    @mock.patch('enterprise.views.get_partial_pipeline')
    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.CourseApiClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    @mock.patch('enterprise.views.organizations_helpers')
    @mock.patch('enterprise.views.CourseCatalogApiClient')
    @mock.patch('enterprise.views.ecommerce_api_client')
    @mock.patch('enterprise.utils.Registry')
    def test_get_course_enrollment_page_with_ecommerce_error(
            self,
            registry_mock,
            ecommerce_api_client_mock,
            course_catalog_client_mock,
            organizations_helpers_mock,
            enrollment_api_client_mock,
            course_api_client_mock,
            configuration_helpers_mock,
            *args
    ):  # pylint: disable=unused-argument
        # Set up Ecommerce API client that returns an error
        broken_price_details_mock = mock.MagicMock()
        method_name = 'baskets.calculate.get'
        attrs = {method_name + '.side_effect': HttpClientError()}
        broken_price_details_mock.configure_mock(**attrs)
        ecommerce_api_client_mock.return_value = broken_price_details_mock

        # Set up course catalog API client
        self._setup_course_catalog_client(course_catalog_client_mock)

        # Set up organizations API client
        self._setup_organizations_client(organizations_helpers_mock)

        configuration_helpers_mock.get_value.return_value = 'edX'

        # Set up course API client
        self._setup_course_api_client(course_api_client_mock)

        # Set up enrollment API client
        self._setup_enrollment_client(enrollment_api_client_mock)

        # Get landing page
        course_id = self.demo_course_id
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        faker = FakerFactory.create()
        provider_id = faker.slug()
        self._setup_registry_mock(registry_mock, provider_id)
        EnterpriseCustomerIdentityProviderFactory(provider_id=provider_id, enterprise_customer=enterprise_customer)
        enterprise_landing_page_url = reverse(
            'enterprise_course_enrollment_page',
            args=[enterprise_customer.uuid, course_id],
        )
        self._login()
        response = self.client.get(enterprise_landing_page_url)
        assert response.status_code == 200

        # Set up expected context
        course_modes = [
            {
                "mode": "professional",
                "title": "Professional Track",
                "original_price": "$100",
                "min_price": 100,
                "sku": "sku-professional",
                "final_price": "$100",
                "description": "Earn a verified certificate!",
                "premium": True,
            }
        ]
        expected_context = {
            'platform_name': 'edX',
            'page_title': 'Choose Your Track',
            'course_id': course_id,
            'course_name': self.dummy_demo_course_details_data['name'],
            'course_organization': self.dummy_demo_course_details_data['org'],
            'course_short_description': self.dummy_demo_course_details_data['short_description'],
            'course_pacing': 'Instructor-Paced',
            'course_start_date': parse(self.dummy_demo_course_details_data['start']).strftime('%B %d, %Y'),
            'course_image_uri': self.dummy_demo_course_details_data['media']['course_image']['uri'],
            'enterprise_customer': enterprise_customer,
            'enterprise_welcome_text': (
                "<strong>Starfleet Academy</strong> has partnered with <strong>edX</strong> to "
                "offer you high-quality learning opportunities from the world's best universities."
            ),
            'confirmation_text': 'Confirm your course',
            'starts_at_text': 'Starts',
            'view_course_details_text': 'View Course Details',
            'select_mode_text': 'Please select one:',
            'price_text': 'Price',
            'continue_link_text': 'Continue',
            'course_modes': course_modes,
            'course_effort': '6 hours per week, per course',
            'level_text': 'Level',
            'effort_text': 'Effort',
            'course_overview': None,
            'organization_logo': 'logo.png',
            'organization_name': 'Organization',
            'course_level_type': 'Type 1',
            'close_modal_button_text': 'Close',
            'premium_modes': course_modes,
        }

        # Compare expected context with response result
        for key, value in expected_context.items():
            assert response.context[key] == value  # pylint: disable=no-member


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
            },
            {
                "slug": "audit",
                "name": "Audit Track",
                "min_price": 0,
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

    @mock.patch('enterprise.views.get_partial_pipeline')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
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
        provider_id = faker.slug()
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

    @mock.patch('enterprise.views.get_partial_pipeline')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
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
        enrollment_client.get_course_modes.side_effect = HttpClientError
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
            enable_audit_enrollment=True,
        )
        faker = FakerFactory.create()
        provider_id = faker.slug()
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

    @mock.patch('enterprise.views.get_partial_pipeline')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
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
        provider_id = faker.slug()
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

    @mock.patch('enterprise.views.get_partial_pipeline')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
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
        provider_id = faker.slug()
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

    @mock.patch('enterprise.views.get_partial_pipeline')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
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
        provider_id = faker.slug()
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

    @mock.patch('enterprise.views.get_partial_pipeline')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
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
        provider_id = faker.slug()
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
