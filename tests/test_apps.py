# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` models module.
"""

from __future__ import absolute_import, unicode_literals, with_statement

import unittest

import integrated_channels
import mock
from pytest import mark

from django.contrib.auth.models import User
from django.db.models.signals import pre_migrate

import enterprise
from test_utils.factories import EnterpriseCustomerFactory, UserFactory


@mark.django_db
class TestEnterpriseConfig(unittest.TestCase):
    """
    Test edx-enterprise app config.
    """

    def setUp(self):
        """
        Set up test environment.
        """
        super(TestEnterpriseConfig, self).setUp()
        self.post_save_mock = mock.Mock()
        patcher = mock.patch('enterprise.signals.handle_user_post_save', self.post_save_mock)
        patcher.start()
        self.app_config = enterprise.apps.EnterpriseConfig('enterprise', enterprise)
        self.addCleanup(patcher.stop)

    def test_ready_connects_user_post_save_handler(self):
        self.app_config.ready()

        user = UserFactory()

        assert self.post_save_mock.call_count == 1
        call_args, call_kwargs = self.post_save_mock.call_args_list[0]
        assert call_args == ()
        assert call_kwargs["sender"] == User
        assert call_kwargs["instance"] == user
        assert call_kwargs["created"]

    def test_ready_does_not_fire_user_post_save_handler_for_other_models(self):
        self.app_config.ready()
        EnterpriseCustomerFactory()

        assert not self.post_save_mock.called

    def test_ready_disconnects_user_post_save_handler_for_migration(self):
        self.app_config.ready()
        pre_migrate.send(mock.Mock())

        UserFactory()

        assert not self.post_save_mock.called


@mark.django_db
class TestIntegratedChannelConfig(unittest.TestCase):
    """
    Test integrated_channels.integrated_channel app config.
    """

    def setUp(self):
        """
        Set up test environment
        """
        super(TestIntegratedChannelConfig, self).setUp()
        self.app_config = integrated_channels.integrated_channel.apps.IntegratedChannelConfig(
            'integrated_channel', integrated_channels.integrated_channel
        )

    def test_name(self):
        assert self.app_config.name == 'integrated_channel'


@mark.django_db
class TestSAPSuccessFactorsConfig(unittest.TestCase):
    """
    Test integrated_channels.sap_success_factors app config.
    """

    def setUp(self):
        """
        Set up test environment
        """
        super(TestSAPSuccessFactorsConfig, self).setUp()
        self.app_config = integrated_channels.sap_success_factors.apps.SAPSuccessFactorsConfig(
            'sap_success_factors', integrated_channels.sap_success_factors
        )

    def test_name(self):
        assert self.app_config.name == 'sap_success_factors'


@mark.django_db
class TestDegreedConfig(unittest.TestCase):
    """
    Test integrated_channels.degreed app config.
    """

    def setUp(self):
        """
        Set up test environment
        """
        super(TestDegreedConfig, self).setUp()
        self.app_config = integrated_channels.degreed.apps.DegreedConfig(
            'degreed', integrated_channels.degreed
        )

    def test_name(self):
        assert self.app_config.name == 'degreed'
