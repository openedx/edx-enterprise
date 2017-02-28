"""
Module tests user-facing views of the Enterprise app.
"""
from __future__ import absolute_import, unicode_literals

import unittest

import ddt
import mock
from pytest import mark, raises

from django.core.urlresolvers import NoReverseMatch, reverse
from django.shortcuts import render_to_response
from django.test import Client

from enterprise.models import EnterpriseCourseEnrollment, EnterpriseCustomerUser, UserDataSharingConsentAudit
from enterprise.utils import NotConnectedToOpenEdx
from enterprise.views import GrantDataSharingPermissions, HttpClientError
from test_utils.factories import EnterpriseCustomerFactory, EnterpriseCustomerUserFactory, UserFactory


def fake_render(template, context, request):  # pylint: disable=unused-argument
    """
    Switch the request to use the Django rendering engine instead of Mako.
    """
    return render_to_response('enterprise/grant_data_sharing_permissions.html', context=context)


@mark.django_db
@ddt.ddt
class TestGrantDataSharingPermissions(unittest.TestCase):
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

    def test_get_warning(self):
        """
        Check that ``get_warning`` gives us the correct message.
        """
        platform = 'my platform'
        provider = 'your provider'
        assert GrantDataSharingPermissions.get_warning(provider, platform, True) == (
            "Are you sure? If you do not agree to share your data, you will have to use "
            "another account to access my platform."
        )
        assert GrantDataSharingPermissions.get_warning(provider, platform, False) == (
            "Are you sure? If you do not agree to share your data, you will not receive "
            "discounts from your provider."
        )

    def test_get_note(self):
        """
        Test that ``get_note`` gives us the correct message.
        """
        provider = 'Your provider'
        assert GrantDataSharingPermissions.get_note(provider, True) == (
            "Your provider requires data sharing consent; if consent is not provided, you will"
            " be redirected to log in page."
        )
        assert GrantDataSharingPermissions.get_note(provider, False) == (
            "Your provider requests data sharing consent; if consent is not provided, you will"
            " not be able to get any discounts from Your provider."
        )

    def test_get_no_patches(self):
        """
        Test that we get the right exception when nothing is patched.
        """
        client = Client()
        with raises(NotConnectedToOpenEdx) as excinfo:
            client.get(self.url)
        assert str(excinfo.value) == 'Methods in the Open edX platform necessary for this view are not available.'

    @mock.patch('enterprise.views.get_pipeline_partial')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.get_complete_url')
    @mock.patch('enterprise.views.render_to_response', side_effect=fake_render)
    @mock.patch('enterprise.views.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.configuration_helpers')
    def test_get_no_customer_404(
            self,
            config_mock,
            get_ec_mock,
            render_mock,
            mock_url,
            mock_social,
            mock_quarantine,
            mock_lift,
            mock_partial,
    ):  # pylint: disable=unused-argument
        """
        Test that we have the appropriate context when rendering the form.
        """
        config_mock.get_value.return_value = 'This Platform'
        get_ec_mock.return_value = None
        client = Client()
        response = client.get(self.url)
        assert response.status_code == 404

    @mock.patch('enterprise.views.get_pipeline_partial')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.get_complete_url')
    @mock.patch('enterprise.views.render_to_response', side_effect=fake_render)
    @mock.patch('enterprise.views.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.configuration_helpers')
    def test_get_render_patched(
            self,
            config_mock,
            get_ec_mock,
            render_mock,
            mock_url,
            mock_social,
            mock_quarantine,
            mock_lift,
            mock_partial,
    ):  # pylint: disable=unused-argument
        """
        Test that we have the appropriate context when rendering the form.
        """
        config_mock.get_value.return_value = 'This Platform'
        fake_ec = mock.MagicMock(
            enforces_data_sharing_consent=mock.MagicMock(return_value=True)
        )
        fake_ec.name = 'Fake Customer Name'
        get_ec_mock.return_value = fake_ec
        client = Client()
        response = client.get(self.url)
        expected_warning = (
            "Are you sure? If you do not agree to share your data, you will have to use "
            "another account to access This Platform."
        )
        expected_note = (
            "Fake Customer Name requires data sharing consent; if consent is not provided, you will"
            " be redirected to log in page."
        )
        expected_context = {
            'platform_name': 'This Platform',
            'enterprise_customer_name': 'Fake Customer Name',
            'data_sharing_consent': 'required',
            'messages': {
                'warning': expected_warning,
                'note': expected_note
            }
        }
        for key, value in expected_context.items():
            assert response.context[key] == value  # pylint: disable=no-member

    @mock.patch('enterprise.views.get_pipeline_partial')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.get_complete_url')
    @mock.patch('enterprise.views.render_to_response', side_effect=fake_render)
    @mock.patch('enterprise.views.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.configuration_helpers')
    def test_get_render_patched_optional(
            self,
            config_mock,
            get_ec_mock,
            render_mock,
            mock_url,
            mock_social,
            mock_quarantine,
            mock_lift,
            mock_partial,
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
        expected_warning = (
            "Are you sure? If you do not agree to share your data, you will not receive "
            "discounts from Fake Customer Name."
        )
        expected_note = (
            "Fake Customer Name requests data sharing consent; if consent is not provided, you will"
            " not be able to get any discounts from Fake Customer Name."
        )
        expected_context = {
            'platform_name': 'This Platform',
            'enterprise_customer_name': 'Fake Customer Name',
            'data_sharing_consent': 'optional',
            'messages': {
                'warning': expected_warning,
                'note': expected_note
            }
        }
        for key, value in expected_context.items():
            assert response.context[key] == value  # pylint: disable=no-member

    @mock.patch('enterprise.views.get_pipeline_partial')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.render_to_response')
    @mock.patch('enterprise.views.get_complete_url')
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.get_enterprise_customer_for_request')
    def test_post_no_customer_404(
            self,
            mock_get_ec,
            mock_get_rsa,
            mock_get_ec2,
            mock_url,
            mock_render,
            mock_config,
            mock_lift,
            mock_quarantine,
            mock_partial,
    ):  # pylint: disable=unused-argument
        """
        Test that when there's no customer for the request, POST gives a 404.
        """
        mock_get_ec.return_value = None
        client = Client()
        response = client.post(self.url)
        assert response.status_code == 404

    @mock.patch('enterprise.views.get_pipeline_partial')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.render_to_response')
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
            mock_pipeline_partial,
    ):  # pylint: disable=unused-argument
        """
        Test that when there's no customer for the request, POST gives a 404.
        """
        mock_get_ec.return_value = True
        mock_get_rsa.return_value = None
        client = Client()
        response = client.post(self.url)
        assert response.status_code == 404

    @mock.patch('enterprise.views.get_pipeline_partial')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.render_to_response')
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
            mock_partial,
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

    @mock.patch('enterprise.views.get_pipeline_partial')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.render_to_response')
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
            mock_partial,
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

    @mock.patch('enterprise.views.get_pipeline_partial')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.render_to_response')
    @mock.patch('enterprise.views.get_complete_url')
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.get_enterprise_customer_for_request')
    def test_post_patch_real_social_auth_enabled(
            self,
            mock_get_ec,
            mock_get_rsa,
            mock_get_ec2,
            mock_url,
            mock_render,
            mock_config,
            mock_lift,
            mock_quarantine,
            mock_partial,
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
        mock_partial.return_value = {'backend': 'fake_backend'}
        response = client.post(self.url, {'data_sharing_consent': True})
        assert UserDataSharingConsentAudit.objects.all().count() == 1
        assert EnterpriseCustomerUser.objects.all().count() == 1
        assert UserDataSharingConsentAudit.objects.all()[0].enabled
        assert response.status_code == 302

    def _login(self):
        """
        Log user in.
        """
        assert self.client.login(username=self.user.username, password="QWERTY")

    @mock.patch('enterprise.views.get_pipeline_partial')
    @mock.patch('enterprise.views.get_complete_url')
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.render_to_response', side_effect=fake_render)
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
        for key, value in {
                "platform_name": "My Platform",
                "data_sharing_consent": "required",
                "messages": {
                    "note": (
                        "Courses from Starfleet Academy require data sharing consent. If you do not agree to "
                        "share your data, you will be redirected to your dashboard."
                    ),
                    "warning": (
                        "Are you sure? If you do not agree to share your data "
                        "with Starfleet Academy, you cannot access edX Demo Course."
                    ),
                },
                "course_id": "course-v1:edX+DemoX+Demo_Course",
                "course_name": "edX Demo Course",
                "redirect_url": "https://google.com",
                "enterprise_customer_name": ecu.enterprise_customer.name,
                "course_specific": True,
                "enrollment_deferred": enrollment_deferred,
        }.items():
            assert response.context[key] == value  # pylint:disable=no-member

    @mock.patch('enterprise.views.get_pipeline_partial')
    @mock.patch('enterprise.views.get_complete_url')
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.render_to_response', side_effect=fake_render)
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

    @mock.patch('enterprise.views.get_pipeline_partial')
    @mock.patch('enterprise.views.get_complete_url')
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.render_to_response', side_effect=fake_render)
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
        assert response.status_code == 404

    @mock.patch('enterprise.views.get_pipeline_partial')
    @mock.patch('enterprise.views.get_complete_url')
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.render_to_response', side_effect=fake_render)
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

    @mock.patch('enterprise.views.get_pipeline_partial')
    @mock.patch('enterprise.views.get_complete_url')
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.render_to_response', side_effect=fake_render)
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

    @mock.patch('enterprise.views.get_pipeline_partial')
    @mock.patch('enterprise.views.get_complete_url')
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.render_to_response', side_effect=fake_render)
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

    @mock.patch('enterprise.views.get_pipeline_partial')
    @mock.patch('enterprise.views.get_complete_url')
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.render_to_response', side_effect=fake_render)
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

    @mock.patch('enterprise.views.get_pipeline_partial')
    @mock.patch('enterprise.views.get_complete_url')
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.render_to_response', side_effect=fake_render)
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
        assert resp.status_code == 404

    @mock.patch('enterprise.views.get_pipeline_partial')
    @mock.patch('enterprise.views.get_complete_url')
    @mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.get_real_social_auth_object')
    @mock.patch('enterprise.views.get_enterprise_customer_for_request')
    @mock.patch('enterprise.views.quarantine_session')
    @mock.patch('enterprise.views.lift_quarantine')
    @mock.patch('enterprise.views.configuration_helpers')
    @mock.patch('enterprise.views.render_to_response', side_effect=fake_render)
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
