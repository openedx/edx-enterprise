# -*- coding: utf-8 -*-
"""
Django management command for saving EnterpriseCustomerUser models.
"""

import logging

from django.core.management import BaseCommand

from enterprise.models import EnterpriseCustomerUser

LOGGER = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Calls save() on EnterpriseCustomerUser models.

    This is useful for triggering save-related signals causing the
    associated signal receiver functions to fire.
    """
    help = 'Save existing EnterpriseCustomerUser models.'

    def add_arguments(self, parser):
        parser.add_argument(
            '-e',
            '--enterprise_customer_uuid',
            action='store',
            dest='enterprise_customer_uuid',
            default=None,
            help='Run this command for only the given EnterpriseCustomer UUID.'
        )

    def handle(self, *args, **options):
        enterprise_customer_filter = {}
        enterprise_customer_uuid = options.get('enterprise_customer_uuid')
        if enterprise_customer_uuid:
            enterprise_customer_filter['enterprise_customer'] = enterprise_customer_uuid

        count = 0
        for enterprise_customer_user in EnterpriseCustomerUser.objects.filter(**enterprise_customer_filter):
            enterprise_customer_user.save()
            count += 1

        LOGGER.info('%s EnterpriseCustomerUser models saved.', count)
