# -*- coding: utf-8 -*-
"""
Django management command for bulk updating EnterpriseCustomerCatalog record's EnterpriseCatalogQuery's.
"""

import logging
import shlex

from django.core.management import BaseCommand, CommandError

from enterprise.models import (
    BulkCatalogQueryUpdateCommandConfiguration,
    EnterpriseCatalogQuery,
    EnterpriseCustomerCatalog,
)

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
            '-o', '--old_id',
            metavar='OLD_ID',
            dest='old_id',
            help='Old catalog query ID to be replaced.'
        )
        parser.add_argument(
            '-n', '--new_id',
            metavar='NEW_ID',
            dest='new_id',
            help='New catalog query ID to replace the old one.'
        )
        parser.add_argument(
            '--args-from-database',
            action='store_true',
            help='Use arguments from the BulkCatalogQueryUpdateCommandConfiguration model instead of the command line'
        )

    def get_args_from_database(self):
        """
        Returns an options dictionary from the current BulkCatalogQueryUpdateCommandConfiguration model.
        """
        config = BulkCatalogQueryUpdateCommandConfiguration.current()
        if not config.enabled:
            raise CommandError(
                "BulkCatalogQueryUpdateCommandConfiguration is disabled, but --args-from-database was requested"
            )

        args = shlex.split(config.arguments)
        parser = self.create_parser("manage.py", "bulk_updates_catalog_query_id")

        return vars(parser.parse_args(args))

    def handle(self, *args, **options):
        """
        Entry point for management command execution.
        """
        LOGGER.info("Starting bulk update of EnterpriseCatalog's enterprise catalog query IDs")
        if options['args_from_database']:
            options = self.get_args_from_database()

        old_id = options.get('old_id')
        new_id = options.get('new_id')
        if not old_id:
            raise CommandError('You must specify an old query ID')
        if not new_id:
            raise CommandError('You must specify a new query ID')

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
