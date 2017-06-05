"""
Module tests user-facing views of the Enterprise app.
"""
from __future__ import absolute_import, unicode_literals

import ddt
import mock
from dateutil.parser import parse
from pytest import mark, raises

from django.contrib import messages
from django.core.urlresolvers import NoReverseMatch, reverse
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.test import Client, TestCase

from enterprise.models import EnterpriseCourseEnrollment, EnterpriseCustomerUser, UserDataSharingConsentAudit
from enterprise.utils import NotConnectedToEdX
from enterprise.views import (
    CONFIRMATION_ALERT_PROMPT,
    CONFIRMATION_ALERT_PROMPT_WARNING,
    CONSENT_REQUEST_PROMPT,
    GrantDataSharingPermissions,
    HttpClientError,
)
from test_utils.factories import EnterpriseCustomerFactory, EnterpriseCustomerUserFactory, UserFactory


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
        with raises(NotConnectedToEdX) as excinfo:
            client.get(self.url)
        assert str(excinfo.value) == 'Methods in the Open edX platform necessary for this view are not available.'

    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.get_complete_url')
    @mock.patch('enterprise.views.redirect')
    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.configuration_helpers')
    def test_get_no_customer_redirect(
            self,
            config_mock,
            get_ec_mock,
            render_mock,
            redirect_mock,
            mock_url,
            mock_social,
            mock_quarantine,
            mock_lift,
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
            render_mock,
            mock_url,
            mock_social,
            mock_quarantine,
            mock_lift,
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

    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.redirect')
    @mock.patch('enterprise.views.render')
    @mock.patch('enterprise.views.get_complete_url')
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.get_enterprise_customer_for_request')
    def test_post_no_customer_redirect(
            self,
            mock_get_ec,
            mock_get_rsa,
            mock_get_ec2,
            mock_url,
            mock_render,
            mock_redirect,
            mock_config,
            mock_lift,
            mock_quarantine,
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
            mock_get_ec2,
            mock_url,
            mock_render,
            mock_config,
            mock_lift,
            mock_quarantine,
    ):  # pylint: disable=unused-argument
        """
        Test that when there's no customer for the request, POST gives a 404.
        """
        mock_get_ec.return_value = True
        mock_get_rsa.return_value = None
        client = Client()
        response = client.post(self.url)
        assert response.status_code == 404

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
            mock_url,
            mock_render,
            mock_config,
            mock_lift,
            mock_quarantine,
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
            session['partial_pipeline'] = True
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
            mock_render,
            mock_config,
            mock_lift,
            mock_quarantine,
    ):  # pylint: disable=unused-argument
        """
        Test an unenforced request
        """
        customer = EnterpriseCustomerFactory(enable_data_sharing_consent=False)
        mock_get_ec.return_value = customer
        mock_get_ec2.return_value = customer
        mock_get_rsa.return_value = mock.MagicMock(user=UserFactory())
        mock_url.return_value = '/'
        client = Client()
        session = client.session
        session['partial_pipeline'] = {'backend': 'fake_backend'}
        session.save()
        response = client.post(self.url)
        assert UserDataSharingConsentAudit.objects.all().count() == 1
        assert EnterpriseCustomerUser.objects.all().count() == 1
        assert not UserDataSharingConsentAudit.objects.all()[0].enabled
        assert response.status_code == 302

    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.render')
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
            mock_render,
            mock_config,
            mock_lift,
            mock_quarantine,
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
        session = client.session
        session['partial_pipeline'] = {'backend': 'fake_backend'}
        session.save()
        response = client.post(self.url, {'data_sharing_consent': True})
        assert UserDataSharingConsentAudit.objects.all().count() == 1
        assert EnterpriseCustomerUser.objects.all().count() == 1
        assert UserDataSharingConsentAudit.objects.all()[0].enabled
        assert response.status_code == 302

        # Now verify that response contains the expected messages when a
        # learner is linked with an enterprise
        self._assert_enterprise_linking_messages(response, user_is_active)

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
            mock_render,
            mock_config,
            mock_lift,
            mock_quarantine,
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
        session['partial_pipeline'] = {'backend': 'fake_backend'}
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

    @mock.patch('enterprise.views.get_complete_url')
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.render', side_effect=fake_render)
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
            render_mock,  # pylint: disable=unused-argument
            mock_config,
            *args  # pylint: disable=unused-argument
    ):
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
            render_mock,  # pylint: disable=unused-argument
            mock_config,
            *args  # pylint: disable=unused-argument
    ):
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

    @mock.patch('enterprise.views.get_complete_url')
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.CourseApiClient')
    def test_get_course_specific_consent_unauthenticated_user(
            self,
            course_api_client_mock,
            render_mock,  # pylint: disable=unused-argument
            mock_config,
            *args  # pylint: disable=unused-argument
    ):
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

    @mock.patch('enterprise.views.get_complete_url')
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.CourseApiClient')
    def test_get_course_specific_consent_bad_api_response(
            self,
            course_api_client_mock,
            render_mock,  # pylint: disable=unused-argument
            mock_config,
            *args  # pylint: disable=unused-argument
    ):
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

    @mock.patch('enterprise.views.get_complete_url')
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.CourseApiClient')
    def test_get_course_specific_consent_not_needed(
            self,
            course_api_client_mock,
            render_mock,  # pylint: disable=unused-argument
            mock_config,
            *args  # pylint: disable=unused-argument
    ):
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
            *args  # pylint: disable=unused-argument
    ):
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
            *args  # pylint: disable=unused-argument
    ):
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
            *args  # pylint: disable=unused-argument
    ):
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
            *args  # pylint: disable=unused-argument
    ):
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
        }
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
        super(TestCourseEnrollmentView, self).setUp()

    def _login(self):
        """
        Log user in.
        """
        assert self.client.login(username=self.user.username, password="QWERTY")

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.CourseApiClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    def test_get_course_enrollment_page(
            self,
            enrollment_api_client_mock,
            course_api_client_mock,
            lift_quarantine_mock,   # pylint: disable=unused-argument
            quarantine_session_mock,    # pylint: disable=unused-argument
            social_auth_object_mock,   # pylint: disable=unused-argument
            get_ec_for_request_mock,   # pylint: disable=unused-argument
            configuration_helpers_mock,
            render_to_response_mock,    # pylint: disable=unused-argument
    ):
        course_id = self.demo_course_id
        configuration_helpers_mock.get_value.return_value = 'edX'
        client = course_api_client_mock.return_value
        client.get_course_details.return_value = self.dummy_demo_course_details_data
        enrollment_client = enrollment_api_client_mock.return_value
        enrollment_client.get_course_modes.return_value = self.dummy_demo_course_modes
        enrollment_client.get_course_enrollment.return_value = None
        self._login()
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
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
                'final_price': '$100',
                'description': 'Earn a verified certificate!',
                'premium': True,
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

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.CourseApiClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    def test_get_course_specific_enrollment_view_audit_enabled(
            self,
            enrollment_api_client_mock,
            course_api_client_mock,
            lift_quarantine_mock,   # pylint: disable=unused-argument
            quarantine_session_mock,    # pylint: disable=unused-argument
            social_auth_object_mock,   # pylint: disable=unused-argument
            get_ec_for_request_mock,   # pylint: disable=unused-argument
            configuration_helpers_mock,
            render_to_response_mock,    # pylint: disable=unused-argument
    ):
        course_id = self.demo_course_id
        configuration_helpers_mock.get_value.return_value = 'edX'
        client = course_api_client_mock.return_value
        client.get_course_details.return_value = self.dummy_demo_course_details_data
        enrollment_client = enrollment_api_client_mock.return_value
        enrollment_client.get_course_modes.return_value = self.dummy_demo_course_modes
        enrollment_client.get_course_enrollment.return_value = None
        self._login()
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
            enable_audit_enrollment=True,
        )
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
                'final_price': '$100',
                'description': 'Earn a verified certificate!',
                'premium': True,
            },
            {
                'mode': 'audit',
                'title': 'Audit Track',
                'original_price': 'FREE',
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

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.CourseApiClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    def test_get_course_enrollment_page_with_no_start_date(
            self,
            enrollment_api_client_mock,
            course_api_client_mock,
            lift_quarantine_mock,   # pylint: disable=unused-argument
            quarantine_session_mock,    # pylint: disable=unused-argument
            social_auth_object_mock,   # pylint: disable=unused-argument
            get_ec_for_request_mock,   # pylint: disable=unused-argument
            configuration_helpers_mock,
            render_to_response_mock,    # pylint: disable=unused-argument
    ):
        """
        Verify that the context of the enterprise course enrollment page has
        empty course start date if course details has no start date.
        """
        course_id = self.demo_course_id
        configuration_helpers_mock.get_value.return_value = 'edX'
        client = course_api_client_mock.return_value
        dummy_demo_course_details_data = self.dummy_demo_course_details_data
        dummy_demo_course_details_data['start'] = ''
        client.get_course_details.return_value = dummy_demo_course_details_data
        enrollment_client = enrollment_api_client_mock.return_value
        enrollment_client.get_course_modes.return_value = self.dummy_demo_course_modes
        enrollment_client.get_course_enrollment.return_value = None
        self._login()
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
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

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.CourseApiClient')
    def test_get_course_enrollment_page_for_non_existing_course(
            self,
            course_api_client_mock,
            lift_quarantine_mock,   # pylint: disable=unused-argument
            quarantine_session_mock,    # pylint: disable=unused-argument
            social_auth_object_mock,   # pylint: disable=unused-argument
            get_ec_for_request_mock,   # pylint: disable=unused-argument
            configuration_helpers_mock,
            render_to_response_mock,    # pylint: disable=unused-argument
    ):
        """
        Verify that user will see HTTP 404 (Not Found) in case of invalid
        or non existing course.
        """
        configuration_helpers_mock.get_value.return_value = 'edX'
        client = course_api_client_mock.return_value
        client.get_course_details.return_value = None
        self._login()
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        course_enrollment_page_url = reverse(
            'enterprise_course_enrollment_page',
            args=[enterprise_customer.uuid, self.demo_course_id],
        )
        response = self.client.get(course_enrollment_page_url)
        assert response.status_code == 404

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.CourseApiClient')
    def test_get_course_enrollment_page_for_error_in_getting_course(
            self,
            course_api_client_mock,
            lift_quarantine_mock,   # pylint: disable=unused-argument
            quarantine_session_mock,    # pylint: disable=unused-argument
            social_auth_object_mock,   # pylint: disable=unused-argument
            get_ec_for_request_mock,   # pylint: disable=unused-argument
            configuration_helpers_mock,
            render_to_response_mock,    # pylint: disable=unused-argument
    ):
        """
        Verify that user will see HTTP 404 (Not Found) in case of error while
        getting the course details from CourseApiClient.
        """
        configuration_helpers_mock.get_value.return_value = 'edX'
        client = course_api_client_mock.return_value
        client.get_course_details.side_effect = HttpClientError
        self._login()
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        course_enrollment_page_url = reverse(
            'enterprise_course_enrollment_page',
            args=[enterprise_customer.uuid, self.demo_course_id],
        )
        response = self.client.get(course_enrollment_page_url)
        assert response.status_code == 404

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.CourseApiClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    def test_get_course_specific_enrollment_view_with_course_mode_error(
            self,
            enrollment_api_client_mock,
            course_api_client_mock,
            lift_quarantine_mock,   # pylint: disable=unused-argument
            quarantine_session_mock,    # pylint: disable=unused-argument
            social_auth_object_mock,   # pylint: disable=unused-argument
            get_ec_for_request_mock,   # pylint: disable=unused-argument
            configuration_helpers_mock,
            render_to_response_mock,    # pylint: disable=unused-argument
    ):
        """
        Verify that user will see HTTP 404 (Not Found) in case of invalid
        enterprise customer uuid.
        """
        configuration_helpers_mock.get_value.return_value = 'edX'
        client = course_api_client_mock.return_value
        client.get_course_details.return_value = self.dummy_demo_course_details_data
        enrollment_client = enrollment_api_client_mock.return_value
        enrollment_client.get_course_modes.side_effect = HttpClientError
        enrollment_client.get_course_enrollment.return_value = None
        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        self._login()
        course_enrollment_page_url = reverse(
            'enterprise_course_enrollment_page',
            args=[enterprise_customer.uuid, self.demo_course_id],
        )
        response = self.client.get(course_enrollment_page_url)
        assert response.status_code == 404

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.CourseApiClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    def test_get_course_specific_enrollment_view_for_invalid_ec_uuid(
            self,
            enrollment_api_client_mock,
            course_api_client_mock,
            lift_quarantine_mock,   # pylint: disable=unused-argument
            quarantine_session_mock,    # pylint: disable=unused-argument
            social_auth_object_mock,   # pylint: disable=unused-argument
            get_ec_for_request_mock,   # pylint: disable=unused-argument
            configuration_helpers_mock,
            render_to_response_mock,    # pylint: disable=unused-argument
    ):
        """
        Verify that user will see HTTP 404 (Not Found) in case of invalid
        enterprise customer uuid.
        """
        configuration_helpers_mock.get_value.return_value = 'edX'
        client = course_api_client_mock.return_value
        client.get_course_details.return_value = self.dummy_demo_course_details_data
        enrollment_client = enrollment_api_client_mock.return_value
        enrollment_client.get_course_modes.return_value = self.dummy_demo_course_modes
        enrollment_client.get_course_enrollment.return_value = None
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
    def test_get_course_enrollment_page_for_inactive_user(
            self,
            lift_quarantine_mock,   # pylint: disable=unused-argument
            quarantine_session_mock,    # pylint: disable=unused-argument
            social_auth_object_mock,   # pylint: disable=unused-argument
            get_ec_for_request_mock,   # pylint: disable=unused-argument
            configuration_helpers_mock,
            render_to_response_mock,    # pylint: disable=unused-argument
    ):
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
        enterprise_landing_page_url = reverse(
            'enterprise_course_enrollment_page',
            args=[enterprise_customer.uuid, course_id],
        )
        response = self.client.get(enterprise_landing_page_url)
        expected_redirect_url = (
            '/login?next=%2Fenterprise%2F{enterprise_customer_uuid}%2Fcourse%2Fcourse-v1'
            '%253AedX%252BDemoX%252BDemo_Course%2Fenroll%2F%3Ftpa_hint%3DNone'.format(
                enterprise_customer_uuid=enterprise_customer.uuid
            )
        )
        self.assertRedirects(response, expected_redirect_url, fetch_redirect_response=False)

    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.CourseApiClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    def test_get_course_landing_page_for_enrolled_user(
            self,
            enrollment_api_client_mock,
            course_api_client_mock,
            lift_quarantine_mock,  # pylint: disable=unused-argument
            quarantine_session_mock,  # pylint: disable=unused-argument
            social_auth_object_mock,  # pylint: disable=unused-argument
            get_ec_for_request_mock,  # pylint: disable=unused-argument
            configuration_helpers_mock,
    ):
        """
        Verify that the user will be redirected to the course home page when
        the user is already enrolled.
        """
        course_id = self.demo_course_id
        configuration_helpers_mock.get_value.return_value = 'edX'
        client = course_api_client_mock.return_value
        client.get_course_details.return_value = self.dummy_demo_course_details_data
        enrollment_client = enrollment_api_client_mock.return_value
        enrollment_client.get_course_modes.return_value = self.dummy_demo_course_modes
        enrollment_client.get_course_enrollment.return_value = {"course_details": {"course_id": course_id}}
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

    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.CourseApiClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    def test_post_course_specific_enrollment_view(
            self,
            enrollment_api_client_mock,
            course_api_client_mock,
            lift_quarantine_mock,   # pylint: disable=unused-argument
            quarantine_session_mock,    # pylint: disable=unused-argument
            social_auth_object_mock,   # pylint: disable=unused-argument
            get_ec_for_request_mock,   # pylint: disable=unused-argument
            configuration_helpers_mock,
    ):
        course_id = self.demo_course_id
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

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.CourseApiClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    def test_post_course_specific_enrollment_view_incompatible_mode(
            self,
            enrollment_api_client_mock,
            course_api_client_mock,
            lift_quarantine_mock,   # pylint: disable=unused-argument
            quarantine_session_mock,    # pylint: disable=unused-argument
            social_auth_object_mock,   # pylint: disable=unused-argument
            get_ec_for_request_mock,   # pylint: disable=unused-argument
            configuration_helpers_mock,
            render_to_response_mock,    # pylint: disable=unused-argument
    ):
        course_id = self.demo_course_id
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
                    'final_price': '$100',
                    'description': 'Earn a verified certificate!',
                    'premium': True,
                },
                {
                    'mode': 'audit',
                    'title': 'Audit Track',
                    'original_price': 'FREE',
                    'final_price': 'FREE',
                    'description': 'Not eligible for a certificate; does not count toward a MicroMasters',
                    'premium': False,
                }
            ]
        }
        for key, value in expected_context.items():
            assert response.context[key] == value  # pylint: disable=no-member

    @mock.patch('enterprise.views.render', side_effect=fake_render)
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.CourseApiClient')
    @mock.patch('enterprise.views.EnrollmentApiClient')
    def test_post_course_specific_enrollment_view_premium_mode(
            self,
            enrollment_api_client_mock,
            course_api_client_mock,
            lift_quarantine_mock,   # pylint: disable=unused-argument
            quarantine_session_mock,    # pylint: disable=unused-argument
            social_auth_object_mock,   # pylint: disable=unused-argument
            get_ec_for_request_mock,   # pylint: disable=unused-argument
            configuration_helpers_mock,
            render_to_response_mock,    # pylint: disable=unused-argument
    ):
        course_id = self.demo_course_id
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
