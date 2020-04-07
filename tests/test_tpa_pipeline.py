# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` tpa-pipeline module.
"""
from __future__ import absolute_import, unicode_literals

import unittest

import ddt
import mock
from pytest import mark

from django.contrib.messages.storage import fallback
from django.contrib.sessions.backends import cache
from django.test import RequestFactory

from enterprise.models import EnterpriseCustomerUser
from enterprise.tpa_pipeline import get_enterprise_customer_for_running_pipeline, handle_enterprise_logistration
from test_utils.factories import EnterpriseCustomerFactory, EnterpriseCustomerIdentityProviderFactory, UserFactory


@ddt.ddt
@mark.django_db
class TestTpaPipeline(unittest.TestCase):
    """
    Test functions in the tpa_pipeline module.
    """

    def setUp(self):
        ecidp = EnterpriseCustomerIdentityProviderFactory(provider_id='provider_slug')
        self.customer = ecidp.enterprise_customer
        self.user = UserFactory(is_active=True)
        self.request_factory = RequestFactory()
        self.request = self.request_factory.get('/')
        self.request.session = cache.SessionStore()
        super(TestTpaPipeline, self).setUp()

    def get_mocked_sso_backend(self):
        """
        Get a mocked request backend with mocked strategy.
        """
        # Monkey-patch storage for messaging;   pylint: disable=protected-access
        self.request._messages = fallback.FallbackStorage(self.request)

        strategy_mock = mock.MagicMock(request=self.request)
        backend = mock.MagicMock(
            name=None,
            strategy=strategy_mock,
        )
        return backend

    @ddt.data(False, True)
    def test_handle_enterprise_logistration_user_linking(
            self,
            user_is_active,
    ):
        """
        Test that we create an EnterpriseCustomerUser, then return.
        """
        backend = self.get_mocked_sso_backend()
        self.user = UserFactory(is_active=user_is_active)
        with mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_running_pipeline') as fake_get_ec:
            enterprise_customer = EnterpriseCustomerFactory(
                enable_data_sharing_consent=False
            )
            fake_get_ec.return_value = enterprise_customer
            assert handle_enterprise_logistration(backend, self.user) is None
            assert EnterpriseCustomerUser.objects.filter(
                enterprise_customer=enterprise_customer,
                user_id=self.user.id,
                active=True
            ).count() == 1

    @mock.patch('enterprise.tpa_pipeline.is_multiple_user_enterprises_feature_enabled')
    def test_handle_enterprise_logistration_not_user_linking(self, multiple_enterprises_feature):
        """
        Test if there is not any enterprise customer then EnterpriseCustomerUser would not be associated with it.
        """
        backend = self.get_mocked_sso_backend()
        self.user = UserFactory()
        multiple_enterprises_feature.return_value = True
        with mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_running_pipeline') as fake_get_ec:
            enterprise_customer = EnterpriseCustomerFactory(
                enable_data_sharing_consent=False
            )
            fake_get_ec.return_value = None
            assert handle_enterprise_logistration(backend, self.user) is None
            assert EnterpriseCustomerUser.objects.filter(
                enterprise_customer=enterprise_customer,
                user_id=self.user.id,
                active=True
            ).count() == 0

    def test_handle_enterprise_logistration_user_multiple_enterprises_linking(self):
        """
        Test that if user has multiple enterprise_customers then active status of latest
         enterprise_customer with which user is logged in will be marked as True and active
          status of other enterprise_customers will be marked as False.
        """
        backend = self.get_mocked_sso_backend()
        self.user = UserFactory(is_active=True)
        with mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_running_pipeline') as fake_get_ec:
            enterprise_customer = EnterpriseCustomerFactory(
                enable_data_sharing_consent=False
            )
            enterprise_customer_old = EnterpriseCustomerFactory(
                enable_data_sharing_consent=False
            )
            EnterpriseCustomerUser.objects.create(
                enterprise_customer=enterprise_customer_old,
                user_id=self.user.id,
                active=True
            )
            fake_get_ec.return_value = enterprise_customer
            assert handle_enterprise_logistration(backend, self.user) is None
            assert EnterpriseCustomerUser.objects.filter(
                enterprise_customer=enterprise_customer,
                user_id=self.user.id,
                active=True
            ).count() == 1
            assert EnterpriseCustomerUser.objects.filter(
                enterprise_customer=enterprise_customer_old,
                user_id=self.user.id,
                active=False
            ).count() == 1

    @ddt.data(
        (False, True, 'facebook'),
        (True, False, 'facebook'),
        (True, False, 'facebook'),
        (False, True, 'facebook'),
        (True, True, 'google-oauth2'),
        (False, False, 'google-oauth2'),
        (False, True, 'google-oauth2'),
        (True, False, 'google-oauth2'),
    )
    @ddt.unpack
    @mock.patch('enterprise.tpa_pipeline.is_multiple_user_enterprises_feature_enabled')
    def test_social_auth_user_login_associated_with_multiple_enterprise(self,
                                                                        new_association,
                                                                        multiple_enterprise_switch,
                                                                        backend_name,
                                                                        multiple_enterprises_feature):
        """
        Test redirect to enterprise selection page, if socialAuth user has LMS attached account
        and part of multiple enterprises
        """
        kwargs = {'new_association': new_association}
        backend = self.get_mocked_sso_backend()
        backend.name = backend_name
        backend.strategy.session_get.return_value = 'not-an-enrollment-url'
        self.user = UserFactory(is_active=True)
        multiple_enterprises_feature.return_value = multiple_enterprise_switch
        enterprise_customer = EnterpriseCustomerFactory(
            enable_data_sharing_consent=False
        )
        enterprise_customer_old = EnterpriseCustomerFactory(
            enable_data_sharing_consent=False
        )
        EnterpriseCustomerUser.objects.create(
            enterprise_customer=enterprise_customer_old,
            user_id=self.user.id,
            active=False
        )
        EnterpriseCustomerUser.objects.create(
            enterprise_customer=enterprise_customer,
            user_id=self.user.id,
            active=True
        )
        with mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_running_pipeline') as fake_get_ec:
            with mock.patch('enterprise.tpa_pipeline.select_enterprise_page_as_redirect_url') as ent_page_redirect:  # pylint: disable=invalid-name
                fake_get_ec.return_value = None
                handle_enterprise_logistration(backend, self.user, **kwargs)
                if new_association or not multiple_enterprise_switch:
                    ent_page_redirect.assert_not_called()
                else:
                    ent_page_redirect.called_once()

    @ddt.data(
        (False, 'facebook'),
        (False, 'google-oauth2'),
    )
    @ddt.unpack
    @mock.patch('enterprise.tpa_pipeline.is_multiple_user_enterprises_feature_enabled')
    def test_social_auth_user_login_associated_with_one_enterprise(self, new_association, backend_name,
                                                                   multiple_enterprises_feature):
        """
        Test that if socialAuth user has edx attached account and is part of one enterprises then redirection url
        is not changed
        """
        kwargs = {'new_association': new_association}
        backend = self.get_mocked_sso_backend()
        backend.name = backend_name
        backend.strategy.session_get.return_value = 'not-an-enrollment-url'
        self.user = UserFactory(is_active=True)
        multiple_enterprises_feature.return_value = True
        enterprise_customer = EnterpriseCustomerFactory(
            enable_data_sharing_consent=False
        )

        EnterpriseCustomerUser.objects.create(
            enterprise_customer=enterprise_customer,
            user_id=self.user.id,
            active=False
        )
        with mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_running_pipeline') as fake_get_ec:
            with mock.patch('enterprise.tpa_pipeline.select_enterprise_page_as_redirect_url') as ent_page_redirect:  # pylint: disable=invalid-name
                fake_get_ec.return_value = None
                handle_enterprise_logistration(backend, self.user, **kwargs)
                ent_page_redirect.assert_not_called()

    @ddt.data(
        (True, False, True, 'facebook'),
        (False, False, True, 'facebook'),
        (True, True, False, 'facebook'),
        (False, True, False, 'facebook'),
        (True, True, False, 'facebook'),
        (False, True, False, 'facebook'),
        (True, False, True, 'facebook'),
        (False, False, True, 'facebook'),
        (True, True, True, 'google-oauth2'),
        (False, True, True, 'google-oauth2'),
        (True, False, False, 'google-oauth2'),
        (False, False, False, 'google-oauth2'),
        (True, False, True, 'google-oauth2'),
        (False, False, True, 'google-oauth2'),
        (True, True, False, 'google-oauth2'),
        (False, True, False, 'google-oauth2'),
    )
    @ddt.unpack
    @mock.patch('enterprise.tpa_pipeline.is_multiple_user_enterprises_feature_enabled')
    def test_bypass_enterprise_selection_page_for_enrollment_url_login(self,
                                                                       using_enrollment_url,
                                                                       new_association,
                                                                       multiple_enterprise_switch,
                                                                       backend_name,
                                                                       multiple_enterprises_feature):
        """
        Test that enterprise selection page is bypassed if socialAuth user is part of multiple enterprises
        and uses an enrollment url for login
        """
        kwargs = {'new_association': new_association}
        backend = self.get_mocked_sso_backend()
        backend.name = backend_name
        if using_enrollment_url:
            backend.strategy.session_get.return_value = '/enterprise/12e87171-fb0a/course/course-v1:Test/enroll'
        else:
            backend.strategy.session_get.return_value = 'not-an-enrollment-url'
        self.user = UserFactory(is_active=True)
        multiple_enterprises_feature.return_value = multiple_enterprise_switch
        enterprise_customer = EnterpriseCustomerFactory(
            enable_data_sharing_consent=False
        )
        enterprise_customer_old = EnterpriseCustomerFactory(
            enable_data_sharing_consent=False
        )
        EnterpriseCustomerUser.objects.create(
            enterprise_customer=enterprise_customer_old,
            user_id=self.user.id,
            active=False
        )
        EnterpriseCustomerUser.objects.create(
            enterprise_customer=enterprise_customer,
            user_id=self.user.id,
            active=True
        )
        with mock.patch('enterprise.tpa_pipeline.get_enterprise_customer_for_running_pipeline') as fake_get_ec:
            with mock.patch(
                    'enterprise.tpa_pipeline.select_enterprise_page_as_redirect_url') as ent_page_redirect:  # pylint: disable=invalid-name
                fake_get_ec.return_value = None
                handle_enterprise_logistration(backend, self.user, **kwargs)
                if new_association or not multiple_enterprise_switch or using_enrollment_url:
                    ent_page_redirect.assert_not_called()
                else:
                    ent_page_redirect.called_once()

    def test_get_ec_for_pipeline(self):
        """
        Test that we get the correct results for a given running pipeline.
        """
        with mock.patch('enterprise.tpa_pipeline.Registry') as fake_registry:
            provider = mock.MagicMock(provider_id='provider_slug')
            fake_registry.get_from_pipeline.return_value = provider
            assert get_enterprise_customer_for_running_pipeline(self.request, 'pipeline') == self.customer

            # pipeline is None
            assert get_enterprise_customer_for_running_pipeline(self.request, None) is None

            # provider_id is None
            provider = mock.MagicMock(provider_id=None)
            fake_registry.get_from_pipeline.return_value = provider
            assert get_enterprise_customer_for_running_pipeline(self.request, 'pipeline') is None
