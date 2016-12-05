"""
Module tests user-facing views of the Enterprise app.
"""
from __future__ import absolute_import, unicode_literals

import unittest

import mock
from pytest import mark, raises

from django.core.urlresolvers import NoReverseMatch, reverse
from django.shortcuts import render_to_response
from django.test import Client

from enterprise.models import EnterpriseCustomerUser, UserDataSharingConsentAudit
from enterprise.utils import NotConnectedToEdX
from enterprise.views import GrantDataSharingPermissions
from test_utils.factories import EnterpriseCustomerFactory, UserFactory


def fake_render(template, context, request):  # pylint: disable=unused-argument
    """
    Switch the request to use the Django rendering engine instead of Mako.
    """
    return render_to_response('enterprise/grant_data_sharing_permissions.html', context=context)


@mark.django_db
class TestGrantDataSharingPermissions(unittest.TestCase):
    """
    Test GrantDataSharingPermissions.
    """

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
            "Are you sure? If you do not agree to share your data, you will not get any "
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
        with raises(NotConnectedToEdX) as excinfo:
            client.get(self.url)
        assert str(excinfo.value) == 'Methods in the OpenEdX platform necessary for this view are not available.'

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
    ):  # pylint: disable=unused-argument
        """
        Test that we have the appropriate context when rendering the form.
        """
        config_mock.get_value.return_value = 'This Platform'
        get_ec_mock.return_value = None
        client = Client()
        response = client.get(self.url)
        assert response.status_code == 404

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
            'sso_provider': 'Fake Customer Name',
            'data_sharing_consent': 'required',
            'messages': {
                'warning': expected_warning,
                'note': expected_note
            }
        }
        for key, value in expected_context.items():
            assert response.context[key] == value  # pylint: disable=no-member

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
            "Are you sure? If you do not agree to share your data, you will not get any "
            "discounts from Fake Customer Name."
        )
        expected_note = (
            "Fake Customer Name requests data sharing consent; if consent is not provided, you will"
            " not be able to get any discounts from Fake Customer Name."
        )
        expected_context = {
            'platform_name': 'This Platform',
            'sso_provider': 'Fake Customer Name',
            'data_sharing_consent': 'optional',
            'messages': {
                'warning': expected_warning,
                'note': expected_note
            }
        }
        for key, value in expected_context.items():
            assert response.context[key] == value  # pylint: disable=no-member

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
    ):  # pylint: disable=unused-argument
        """
        Test that when there's no customer for the request, POST gives a 404.
        """
        mock_get_ec.return_value = None
        client = Client()
        response = client.post(self.url)
        assert response.status_code == 404

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
        assert UserDataSharingConsentAudit.objects.all().count() == 1
        assert EnterpriseCustomerUser.objects.all().count() == 1
        assert not UserDataSharingConsentAudit.objects.all()[0].enabled

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
        response = client.post(self.url, {'data_sharing_consent': True})
        assert UserDataSharingConsentAudit.objects.all().count() == 1
        assert EnterpriseCustomerUser.objects.all().count() == 1
        assert UserDataSharingConsentAudit.objects.all()[0].enabled
        assert response.status_code == 302
