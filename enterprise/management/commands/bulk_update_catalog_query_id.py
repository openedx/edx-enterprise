# -*- coding: utf-8 -*-
"""
Django management command for bulk updating EnterpriseCustomerCatalog record's EnterpriseCatalogQuery's.
"""

import logging

from django.core.management import BaseCommand

from enterprise.models import EnterpriseCatalogQuery, EnterpriseCustomerCatalog

LOGGER = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Takes a new and old Enterprise Catalog Query ID, find all most recent records within the historical Enterprise
    Catalog table where enterprise catalog query ID is the old ID provided and updates the corresponding Enterprise
    Catalog table entries with the new ID.
    """
    help = "Updates specified EnterpriseCatalog's enterprise catalog query ID records with a provided new ID"

    def add_arguments(self, parser):
        parser.add_argument(
            'old_id',
            action='store',
            help='Old catalog query ID to be replaced.'
        )
        parser.add_argument(
            'new_id',
            action='store',
            help='New catalog query ID to replace the old one.'
        )

    def handle(self, *args, **options):
        """
        Entry point for management command execution.
        """
        LOGGER.info("Starting bulk update of EnterpriseCatalog's enterprise catalog query IDs")

        old_id = options['old_id']
        new_id = options['new_id']
        uuids_to_change = []
        if EnterpriseCatalogQuery.objects.filter(id=new_id).first():
            # pylint: disable=no-member
            catalogs_to_change = EnterpriseCustomerCatalog.history.filter(enterprise_catalog_query_id=old_id).order_by(
                '-modified'
            ).distinct()
            # pylint: enable=no-member
            for catalog in catalogs_to_change:
                if not catalog.next_record and catalog.get_history_type_display() != 'Deleted':
                    uuids_to_change.append(catalog.uuid)

            EnterpriseCustomerCatalog.objects.filter(uuid__in=uuids_to_change).update(
                enterprise_catalog_query_id=new_id
            )
            LOGGER.info(
                "Completed bulk update of EnterpriseCatalog's enterprise catalog queries with ID={} to ID={}".format(
                    old_id,
                    new_id
                )
            )
        else:
            LOGGER.exception("Could not find query with ID={}".format(new_id))
