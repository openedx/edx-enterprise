"""
Backfill missing audit record foreign keys for Cornerstone.
"""
import logging

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils.translation import gettext as _

from integrated_channels.cornerstone.models import (
    CornerstoneEnterpriseCustomerConfiguration,
    CornerstoneLearnerDataTransmissionAudit,
)
from integrated_channels.integrated_channel.management.commands import IntegratedChannelCommandMixin
from integrated_channels.utils import batch_by_pk

LOGGER = logging.getLogger(__name__)


class Command(IntegratedChannelCommandMixin, BaseCommand):
    """
    Management command which backfills missing audit record foreign keys for cornerstone.
    """
    help = _('''
    Backfill missing audit record foreign keys for Cornerstone.
    ''')

    def find_csod_config_by_subdomain(self, customer_subdomain):
        """
        Given the subdomain from a CornerstoneLearnerDataTransmissionAudit record, search the
        CornerstoneEnterpriseCustomerConfiguration records for one with a matching base_url.
        Raise an exception when we dont find exactly one (missing config or duplicate configs are bad)
        """
        # real prod data often has a config like `https://edx.csod.com` alongside `https://edx-stg.csod.com`
        # if we just did a plain `icontains` using `edx` subdomain, we'd get the staging config too
        # expanding the subdomain into a proper url prefix lets us get a more exact match.
        # we require these urls be https
        subdomain_formatted_as_url_prefix = f'https://{customer_subdomain}.'
        configs = CornerstoneEnterpriseCustomerConfiguration.objects.filter(
            cornerstone_base_url__icontains=subdomain_formatted_as_url_prefix,
        )
        if len(configs) > 1:
            LOGGER.error(f'multiple ({len(configs)}) configs found for "{customer_subdomain}" when expecting just 1')
            return None
        else:
            return configs.first()

    def backfill_join_keys(self):
        """
        For each audit record kind, find all the records in batch, then lookup the appropriate
        enterprise_customer_uuid and/or plugin_config_id
        """
        try:
            only_missing_ld_fks = Q(plugin_configuration_id__isnull=True)
            for audit_record_batch in batch_by_pk(CornerstoneLearnerDataTransmissionAudit, extra_filter=only_missing_ld_fks):  # pylint: disable=line-too-long
                for audit_record in audit_record_batch:
                    config = self.find_csod_config_by_subdomain(audit_record.subdomain)
                    if config is None:
                        LOGGER.error(f'cannot find CSOD config for subdomain "{audit_record.subdomain}"')
                        continue
                    ent_cust_uuid = config.enterprise_customer.uuid
                    LOGGER.info(f'CornerstoneLearnerDataTransmissionAudit <{audit_record.pk}> '
                                f'enterprise_customer_uuid={ent_cust_uuid}, '
                                f'plugin_configuration_id={config.id}')
                    audit_record.enterprise_customer_uuid = ent_cust_uuid
                    audit_record.plugin_configuration_id = config.id
                    audit_record.save()
        except Exception as exc:
            LOGGER.exception('backfill_missing_csod_foreign_keys failed', exc_info=exc)
            raise exc

    def handle(self, *args, **options):
        """
        Backfill missing audit record foreign keys.
        """
        self.backfill_join_keys()
