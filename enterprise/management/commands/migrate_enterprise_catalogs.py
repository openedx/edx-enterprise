# -*- coding: utf-8 -*-
"""
Django management command for migrating EnterpriseCustomerCatalog data to new service.
"""

import logging

from django.contrib import auth
from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import ugettext as _

from enterprise.api_client.enterprise_catalog import EnterpriseCatalogApiClient
from enterprise.models import EnterpriseCustomerCatalog

LOGGER = logging.getLogger(__name__)
User = auth.get_user_model()


class Command(BaseCommand):
    """
    Migrate EnterpriseCustomerCatalog data to new Enterprise Catalog service.
    """
    help = 'Migrate EnterpriseCustomerCatalog data to new Enterprise Catalog service.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--api_user',
            dest='api_user',
            required=True,
            metavar='LMS_API_USERNAME',
            help=_('Username of a user authorized to access the Enterprise Catalog API.'),
        )
        parser.add_argument(
            '--catalog_uuids',
            dest='catalog_uuids',
            metavar='ENT_CATALOG_UUIDS',
            help=_('Comma separated list of uuids of enterprise catalogs to migrate.'),
        )
        super().add_arguments(parser)

    def handle(self, *args, **options):
        api_username = options['api_user']
        try:
            user = User.objects.get(username=api_username)
        except User.DoesNotExist as user_exception:
            raise CommandError(
                _('A user with the username {username} was not found.').format(username=api_username)
            ) from user_exception

        client = EnterpriseCatalogApiClient(user=user)

        catalog_uuids_string = options.get('catalog_uuids')
        if catalog_uuids_string:
            catalog_uuids_list = catalog_uuids_string.split(',')
            queryset = EnterpriseCustomerCatalog.objects.filter(uuid__in=catalog_uuids_list)
        else:
            queryset = EnterpriseCustomerCatalog.objects.all()

        for enterprise_catalog in queryset:
            LOGGER.info('Migrating Enterprise Catalog {}'.format(enterprise_catalog.uuid))
            try:
                response = client.get_enterprise_catalog(
                    catalog_uuid=enterprise_catalog.uuid,
                    # Suppress 404 exception since we do not expect the catalog to exist
                    # in enterprise-catalog if it is a new catalog
                    should_raise_exception=False,
                )
                catalog_query = enterprise_catalog.enterprise_catalog_query
                catalog_query_uuid = str(catalog_query.uuid) if catalog_query else None
                if not response:
                    # catalog with matching uuid does NOT exist in enterprise-catalog
                    # service, so we should create a new catalog
                    client.create_enterprise_catalog(
                        str(enterprise_catalog.uuid),
                        str(enterprise_catalog.enterprise_customer.uuid),
                        enterprise_catalog.enterprise_customer.name,
                        enterprise_catalog.title,
                        enterprise_catalog.content_filter,
                        enterprise_catalog.enabled_course_modes,
                        enterprise_catalog.publish_audit_enrollment_urls,
                        catalog_query_uuid,
                    )
                else:
                    # catalog with matching uuid does exist in enterprise-catalog
                    # service, so we should update the existing catalog
                    update_fields = {
                        'enterprise_customer': str(enterprise_catalog.enterprise_customer.uuid),
                        'enterprise_customer_name': enterprise_catalog.enterprise_customer.name,
                        'title': enterprise_catalog.title,
                        'content_filter': enterprise_catalog.content_filter,
                        'enabled_course_modes': enterprise_catalog.enabled_course_modes,
                        'publish_audit_enrollment_urls': enterprise_catalog.publish_audit_enrollment_urls,
                        'catalog_query_uuid': catalog_query_uuid,
                    }
                    client.update_enterprise_catalog(
                        str(enterprise_catalog.uuid),
                        **update_fields,
                    )
                LOGGER.info('Successfully migrated Enterprise Catalog {}'.format(enterprise_catalog.uuid))
            except Exception:  # pylint: disable=broad-except
                LOGGER.exception('Failed to migrate enterprise catalog {}'.format(enterprise_catalog.uuid))
