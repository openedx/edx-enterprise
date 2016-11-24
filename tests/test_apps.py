# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` models module.
"""

from __future__ import absolute_import, unicode_literals, with_statement

import unittest

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
