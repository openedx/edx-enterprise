"""
Django management command to explore Exec Ed inclusion flag migration
"""

import copy
import json
import logging

from django.core.management import BaseCommand

from enterprise.api_client.discovery import CourseCatalogApiServiceClient
from enterprise.api_client.enterprise_catalog import EnterpriseCatalogApiClient
from enterprise.models import EnterpriseCatalogQuery, EnterpriseCustomerCatalog
from integrated_channels.utils import batch_by_pk

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Enumerate the catalog filters and log information about how we might migrate them.
    """

    def handle(self, *args, **options):
        enterprise_catalog_client = EnterpriseCatalogApiClient()
        discovery_client = CourseCatalogApiServiceClient()

        for catalog_query_batch in batch_by_pk(EnterpriseCatalogQuery):
            for catalog_query in catalog_query_batch:
                logger.info(f'{catalog_query.id} {catalog_query.include_exec_ed_2u_courses}')

                if catalog_query.include_exec_ed_2u_courses:
                    logger.info(
                        'compare_discovery_and_enterprise_catalogs '
                        f'query {catalog_query.id} already includes exec ed'
                    )
                    continue

                if catalog_query.content_filter.get('course_type'):
                    logger.info(
                        'compare_discovery_and_enterprise_catalogs '
                        f'query {catalog_query.id} already references course_type somehow'
                    )
                    continue

                new_content_filter = copy.deepcopy(catalog_query.content_filter)
                new_content_filter['course_type__exclude'] = 'executive-education-2u'
                new_content_filter_json = json.dumps(new_content_filter)
                logger.info(
                    'compare_discovery_and_enterprise_catalogs '
                    f'query {catalog_query.id} new filter: {new_content_filter_json}'
                )

        for cusrtomer_catalog_batch in batch_by_pk(EnterpriseCustomerCatalog):
            for customer_catalog in cusrtomer_catalog_batch:
                logger.info(f'{customer_catalog.uuid}')

                if customer_catalog.content_filter.get('course_type'):
                    logger.info(
                        'compare_discovery_and_enterprise_catalogs '
                        f'catalog {customer_catalog.uuid} already references course_type somehow'
                    )
                    continue

                new_content_filter = copy.deepcopy(customer_catalog.content_filter)
                new_content_filter['course_type__exclude'] = 'executive-education-2u'
                new_content_filter_json = json.dumps(new_content_filter)
                discovery_count = discovery_client.get_catalog_results_from_discovery(new_content_filter).get('count')
                enterprise_count = enterprise_catalog_client.get_enterprise_catalog(customer_catalog.uuid).get('count')
                logger.info(
                    'compare_discovery_and_enterprise_catalogs catalog '
                    f'{customer_catalog.uuid} '
                    f'discovery count: {discovery_count}, '
                    f'enterprise count: {enterprise_count}, '
                    f'new filter: {new_content_filter_json}'
                )
