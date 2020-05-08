# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` admin actions module.
"""
from __future__ import absolute_import, unicode_literals

import mock

from django.contrib.admin.sites import AdminSite
from django.test import TestCase
from django.test.client import RequestFactory

from enterprise.admin import EnterpriseCustomerCatalogAdmin
from enterprise.models import EnterpriseCustomerCatalog
from test_utils.factories import EnterpriseCustomerCatalogFactory, UserFactory


class EnterpriseCustomerCatalogAdminTests(TestCase):
    """
    Tests the EnterpriseCustomerCatalogAdmin
    """

    def setUp(self):
        super(EnterpriseCustomerCatalogAdminTests, self).setUp()
        self.catalog_admin = EnterpriseCustomerCatalogAdmin(EnterpriseCustomerCatalog, AdminSite)
        self.request = RequestFactory()
        self.request.user = UserFactory(is_staff=True)
        self.enterprise_catalog = EnterpriseCustomerCatalogFactory()
        self.enterprise_catalog_uuid = self.enterprise_catalog.uuid
        self.form = None  # The form isn't important for the current tests as we don't change any logic there

    @mock.patch('enterprise.admin.EnterpriseCatalogApiClient')
    def test_delete_catalog(self, api_client_mock):
        api_client_mock.return_value = mock.MagicMock()
        api_client_mock.return_value.delete_enterprise_catalog = mock.MagicMock()
        self.catalog_admin.delete_model(self.request, self.enterprise_catalog)

        # Verify the API was called correctly and the catalog was deleted
        api_client_mock.return_value.delete_enterprise_catalog.assert_called_with(self.enterprise_catalog_uuid)
        self.assertFalse(EnterpriseCustomerCatalog.objects.exists())

    @mock.patch('enterprise.admin.EnterpriseCatalogApiClient')
    def test_create_catalog(self, api_client_mock):
        api_client_mock.return_value = mock.MagicMock()
        api_client_mock.return_value.create_enterprise_catalog = mock.MagicMock()

        change = False  # False for creation
        self.catalog_admin.save_model(self.request, self.enterprise_catalog, self.form, change)

        # Verify the API was called and the catalog "was created" (even though it already was)
        # This method is a little weird in that the object is sort of created / not-created at the same time
        api_client_mock.return_value.create_enterprise_catalog.assert_called()
        self.assertEqual(
            EnterpriseCustomerCatalog.objects.get(uuid=self.enterprise_catalog_uuid),
            self.enterprise_catalog
        )

    @mock.patch('enterprise.admin.EnterpriseCatalogApiClient')
    def test_update_catalog_without_existing_service_catalog(self, api_client_mock):
        api_client_mock.return_value = mock.MagicMock()
        api_client_mock.return_value.get_enterprise_catalog.return_value = False
        api_client_mock.return_value.create_enterprise_catalog = mock.MagicMock()

        change = True  # True for updating
        self.catalog_admin.save_model(self.request, self.enterprise_catalog, self.form, change)

        # Verify the API was called and the catalog is the same as there were no real updates
        api_client_mock.return_value.create_enterprise_catalog.assert_called()
        self.assertEqual(
            EnterpriseCustomerCatalog.objects.get(uuid=self.enterprise_catalog_uuid),
            self.enterprise_catalog
        )

    @mock.patch('enterprise.admin.EnterpriseCatalogApiClient')
    def test_update_catalog_with_existing_service_catalog(self, api_client_mock):
        api_client_mock.return_value = mock.MagicMock()
        api_client_mock.return_value.get_enterprise_catalog.return_value = True
        api_client_mock.return_value.update_enterprise_catalog = mock.MagicMock()

        change = True  # True for updating
        self.catalog_admin.save_model(self.request, self.enterprise_catalog, self.form, change)

        # Verify the API was called and the catalog is the same as there were no real updates
        api_client_mock.return_value.update_enterprise_catalog.assert_called()
        self.assertEqual(
            EnterpriseCustomerCatalog.objects.get(uuid=self.enterprise_catalog_uuid),
            self.enterprise_catalog
        )
