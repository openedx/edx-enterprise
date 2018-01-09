# -*- coding: utf-8 -*-
"""
Tests for the djagno management command `save_enterprise_customer_users`.
"""
from __future__ import absolute_import, unicode_literals

import mock
from pytest import mark

from django.contrib.auth.models import User
from django.core.management import call_command
from django.db.models.signals import post_save
from django.test import TestCase

from test_utils.factories import EnterpriseCustomerFactory, EnterpriseCustomerUserFactory, UserFactory


@mark.django_db
class ChangeEnterpriseUserUsernameCommandTests(TestCase):
    """
    Test command `change_enterprise_user_username`.
    """
    command = 'change_enterprise_user_username'

    @mock.patch('enterprise.management.commands.change_enterprise_user_username.LOGGER')
    def test_user_not_enterprise(self, logger_mock):
        """
        Test that the command does not update a user's username if it is not linked to an Enterprise.
        """
        user = UserFactory.create(is_active=True, username='old_username')
        new_username = 'new_username'

        post_save_handler = mock.MagicMock()
        post_save.connect(post_save_handler, sender=User)

        call_command(self.command, user_id=user.id, new_username=new_username)

        logger_mock.info.assert_called_with('User {} must be an Enterprise User.'.format(user.id))
        post_save_handler.assert_not_called()

    @mock.patch('enterprise.management.commands.change_enterprise_user_username.LOGGER')
    def test_username_updated_successfully(self, logger_mock):
        """
        Test that the command updates the user's username when the user is linked to an Enterprise.
        """
        user = UserFactory.create(is_active=True, username='old_username')
        enterprise_customer = EnterpriseCustomerFactory(name='Test EnterpriseCustomer')
        EnterpriseCustomerUserFactory(
            user_id=user.id,
            enterprise_customer=enterprise_customer
        )
        new_username = 'new_username'

        post_save_handler = mock.MagicMock()
        post_save.connect(post_save_handler, sender=User)

        call_command(self.command, user_id=user.id, new_username=new_username)

        logger_mock.info.assert_called_with('User {} has been updated with username {}.'.format(user.id, new_username))
        post_save_handler.assert_called()

        updated_user = User.objects.get(id=user.id)
        assert updated_user.username == new_username
