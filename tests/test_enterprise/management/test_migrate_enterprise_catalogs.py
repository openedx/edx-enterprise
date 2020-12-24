# -*- coding: utf-8 -*-
"""
Tests for the djagno management command `create_enterprise_course_enrollments`.
"""

import mock
from pytest import mark, raises

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from test_utils.factories import EnterpriseCustomerCatalogFactory, EnterpriseCustomerFactory, UserFactory


@mark.django_db
class MigrateEnterpriseCatalogsCommandTests(TestCase):
    """
    Test command `migrate_enterprise_catalogs`.
    """
    command = 'migrate_enterprise_catalogs'

    def setUp(self):
        self.user = UserFactory.create(is_staff=True, is_active=True)
        self.enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
        )
        self.enterprise_catalog = EnterpriseCustomerCatalogFactory(
            enterprise_customer=self.enterprise_customer
        )
        super().setUp()

    @mock.patch('enterprise.management.commands.migrate_enterprise_catalogs.LOGGER')
    @mock.patch('enterprise.management.commands.migrate_enterprise_catalogs.EnterpriseCatalogApiClient')
    def test_enterprise_catalogs_created_success(self, api_client_mock, logger_mock):
        """
        Test that the command calls the enterprise catalog api to create each catalog successfully.
        """
        api_client_mock.return_value = mock.MagicMock()
        api_client_mock.return_value.get_enterprise_catalog.return_value = False
        api_client_mock.return_value.create_enterprise_catalog = mock.MagicMock()
        call_command(self.command, '--api_user', self.user.username)

        api_client_mock.return_value.create_enterprise_catalog.assert_called()
        logger_mock.info.assert_called_with(
            'Successfully migrated Enterprise Catalog {}'.format(self.enterprise_catalog.uuid)
        )

    @mock.patch('enterprise.management.commands.migrate_enterprise_catalogs.LOGGER')
    @mock.patch('enterprise.management.commands.migrate_enterprise_catalogs.EnterpriseCatalogApiClient')
    def test_enterprise_catalogs_created_failure(self, api_client_mock, logger_mock):
        """
        Test that the command catches errors that may occur while creating catalogs with the enterprise catalog api.
        """
        api_client_mock.return_value = mock.MagicMock()
        api_client_mock.return_value.get_enterprise_catalog.return_value = False
        api_client_mock.return_value.create_enterprise_catalog = mock.MagicMock(side_effect=Exception)
        call_command(self.command, '--api_user', self.user.username)

        api_client_mock.return_value.create_enterprise_catalog.assert_called()
        logger_mock.exception.assert_called_with(
            'Failed to migrate enterprise catalog {}'.format(self.enterprise_catalog.uuid)
        )

    @mock.patch('enterprise.management.commands.migrate_enterprise_catalogs.LOGGER')
    @mock.patch('enterprise.management.commands.migrate_enterprise_catalogs.EnterpriseCatalogApiClient')
    def test_enterprise_catalogs_updated_success(self, api_client_mock, logger_mock):
        """
        Test that the command calls the enterprise catalog api to update each catalog successfully.
        """
        api_client_mock.return_value = mock.MagicMock()
        api_client_mock.return_value.get_enterprise_catalog.return_value = True
        api_client_mock.return_value.update_enterprise_catalog = mock.MagicMock()
        call_command(self.command, '--api_user', self.user.username)

        api_client_mock.return_value.update_enterprise_catalog.assert_called()
        logger_mock.info.assert_called_with(
            'Successfully migrated Enterprise Catalog {}'.format(self.enterprise_catalog.uuid)
        )

    @mock.patch('enterprise.management.commands.migrate_enterprise_catalogs.LOGGER')
    @mock.patch('enterprise.management.commands.migrate_enterprise_catalogs.EnterpriseCatalogApiClient')
    def test_enterprise_catalogs_updated_failure(self, api_client_mock, logger_mock):
        """
        Test that the command catches errors that may occur while updating catalogs with the enterprise catalog api.
        """
        api_client_mock.return_value = mock.MagicMock()
        api_client_mock.return_value.get_enterprise_catalog.return_value = True
        api_client_mock.return_value.update_enterprise_catalog = mock.MagicMock(side_effect=Exception)
        call_command(self.command, '--api_user', self.user.username)

        api_client_mock.return_value.update_enterprise_catalog.assert_called()
        logger_mock.exception.assert_called_with(
            'Failed to migrate enterprise catalog {}'.format(self.enterprise_catalog.uuid)
        )

    def test_api_user_doesnt_exist(self):
        """
        Test that the command fails when the provided user is invalid.
        """
        error = 'A user with the username invalid was not found.'
        with raises(CommandError) as excinfo:
            call_command(self.command, '--api_user', 'invalid')
        assert str(excinfo.value) == error
