"""
Django management command to add Exec Ed exclusion flag to catalogs
"""

import logging

from django.core.management import BaseCommand

from enterprise.models import EnterpriseCatalogQuery, EnterpriseCustomerCatalog
from integrated_channels.utils import batch_by_pk

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Enumerate the catalog filters and add course_type exclusions where required
    """

    def handle(self, *args, **options):
        for catalog_query_batch in batch_by_pk(EnterpriseCatalogQuery):
            for catalog_query in catalog_query_batch:
                logger.info(f'{catalog_query.id} {catalog_query.include_exec_ed_2u_courses}')

                if catalog_query.include_exec_ed_2u_courses:
                    logger.info(
                        'add_exec_ed_exclusion_to_catalogs '
                        f'query {catalog_query.id} already includes exec ed'
                    )
                    continue

                if catalog_query.content_filter.get('course_type__exclude'):
                    logger.info(
                        'add_exec_ed_exclusion_to_catalogs '
                        f'query {catalog_query.id} already references course_type__exclude somehow'
                    )
                    continue

                if catalog_query.content_filter.get('course_type'):
                    logger.info(
                        'add_exec_ed_exclusion_to_catalogs '
                        f'query {catalog_query.id} already references course_type somehow'
                    )
                    continue

                if catalog_query.content_filter.get('aggregation_key'):
                    logger.info(
                        'add_exec_ed_exclusion_to_catalogs '
                        f'query {catalog_query.id} references aggregation_key somehow'
                    )
                    continue

                catalog_query.content_filter['course_type__exclude'] = 'executive-education-2u'
                catalog_query.save()
                logger.info(
                    'add_exec_ed_exclusion_to_catalogs '
                    f'updated query {catalog_query.id}'
                )

        for customer_catalog_batch in batch_by_pk(EnterpriseCustomerCatalog):
            for customer_catalog in customer_catalog_batch:
                logger.info(f'{customer_catalog.uuid}')

                if customer_catalog.content_filter is None:
                    logger.info(
                        'add_exec_ed_exclusion_to_catalogs '
                        f'catalog {customer_catalog.uuid} has no content_filter'
                    )
                    continue

                if customer_catalog.content_filter.get('course_type__exclude'):
                    logger.info(
                        'add_exec_ed_exclusion_to_catalogs '
                        f'catalog {customer_catalog.uuid} already references course_type__exclude somehow'
                    )
                    continue

                if customer_catalog.content_filter.get('course_type'):
                    logger.info(
                        'add_exec_ed_exclusion_to_catalogs '
                        f'catalog {customer_catalog.uuid} already references course_type somehow'
                    )
                    continue

                if customer_catalog.content_filter.get('aggregation_key'):
                    logger.info(
                        'add_exec_ed_exclusion_to_catalogs '
                        f'catalog {customer_catalog.uuid} references aggregation_key somehow'
                    )
                    continue

                customer_catalog.content_filter['course_type__exclude'] = 'executive-education-2u'
                customer_catalog.save()
                logger.info(
                    'add_exec_ed_exclusion_to_catalogs '
                    f'updated catalog {customer_catalog.uuid}'
                )
