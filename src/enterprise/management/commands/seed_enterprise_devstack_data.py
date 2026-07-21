"""
Management command for seeding a single enterprise customer and its users in devstack.
"""

import json
import logging
import textwrap

from django.core.management.base import BaseCommand

from enterprise.constants import ENTERPRISE_ADMIN_ROLE, ENTERPRISE_LEARNER_ROLE, ENTERPRISE_OPERATOR_ROLE
from enterprise.devstack_api import (
    ensure_enterprise_groups,
    get_or_create_enterprise_catalog,
    get_or_create_enterprise_customer,
    get_or_create_enterprise_user,
    get_or_create_site,
    link_user_to_enterprise,
)

LOGGER = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Management command for populating Devstack with initial data for enterprise.

    Example usage:
        $ ./manage.py lms seed_enterprise_devstack_data
        $ ./manage.py lms seed_enterprise_devstack_data --enterprise-name "Acme Corp"
    """

    help = '''
    Seeds an enterprise customer, users of various roles and permissions, and initial
    data in devstack for related Enterprise models.
    '''

    def add_arguments(self, parser):
        parser.add_argument(
            '--enterprise-name',
            action='store',
            dest='enterprise_name',
            default='Test Enterprise',
            help='Name of enterprise to be created. Defaults to "Test Enterprise".'
        )

    def handle(self, *args, **options):
        enterprise_name = options['enterprise_name']

        LOGGER.info('\nEnsuring enterprise-related Django groups exist...')
        ensure_enterprise_groups()

        LOGGER.info('\nCreating a new enterprise customer...')
        site = get_or_create_site()
        enterprise_customer = get_or_create_enterprise_customer(name=enterprise_name, site=site)
        enterprise_catalog = get_or_create_enterprise_catalog(enterprise_customer)

        LOGGER.info('\nCreating enterprise users and assigning roles...')
        slug = enterprise_customer.slug
        enterprise_users = [
            get_or_create_enterprise_user(
                username=f'{ENTERPRISE_LEARNER_ROLE}_{slug}',
                role=ENTERPRISE_LEARNER_ROLE,
                enterprise_customer=enterprise_customer,
            ),
            get_or_create_enterprise_user(
                username=f'{ENTERPRISE_ADMIN_ROLE}_{slug}',
                role=ENTERPRISE_ADMIN_ROLE,
                enterprise_customer=enterprise_customer,
            ),
            # Super admin with the admin role on all enterprises.
            get_or_create_enterprise_user(
                username=ENTERPRISE_ADMIN_ROLE,
                role=ENTERPRISE_ADMIN_ROLE,
                applies_to_all_contexts=True,
            ),
            get_or_create_enterprise_user(
                username=ENTERPRISE_OPERATOR_ROLE,
                role=ENTERPRISE_OPERATOR_ROLE,
                applies_to_all_contexts=True,
            ),
            # Service workers as operators for all enterprises.
            get_or_create_enterprise_user(
                username='license-manager_worker',
                role=ENTERPRISE_OPERATOR_ROLE,
                applies_to_all_contexts=True,
            ),
            get_or_create_enterprise_user(
                username='enterprise-catalog_worker',
                role=ENTERPRISE_OPERATOR_ROLE,
                applies_to_all_contexts=True,
            ),
            get_or_create_enterprise_user(
                username='enterprise_worker',
                role=ENTERPRISE_OPERATOR_ROLE,
                applies_to_all_contexts=True,
            ),
            get_or_create_enterprise_user(
                username='ecommerce_worker',
                role=ENTERPRISE_OPERATOR_ROLE,
                applies_to_all_contexts=True,
            ),
        ]
        for i in range(2):
            enterprise_users.append(get_or_create_enterprise_user(
                username=f'{slug}_learner_{i + 1}',
                role=ENTERPRISE_LEARNER_ROLE,
                enterprise_customer=enterprise_customer,
            ))

        LOGGER.info('\nLinking users to enterprise...')
        enterprise_linked_users = []
        for enterprise_user in enterprise_users:
            if enterprise_user is None:
                continue
            ecu, _ = link_user_to_enterprise(enterprise_user['user'], enterprise_customer)
            enterprise_linked_users.append({
                'user_id': ecu.user_id,
                'enterprise_customer_user_id': ecu.id,
                'username': ecu.username,
            })

        LOGGER.info(
            textwrap.dedent(
                '''\nSuccessfully created a new enterprise with the following data:
                \n| Enterprise Customer: %s (%s)
                \n| Enterprise Catalog: %s (%s)
                \n| Enterprise Users (%i): %s
                '''
            ),
            enterprise_customer.name,
            enterprise_customer.uuid,
            enterprise_catalog.title,
            enterprise_catalog.uuid,
            len(enterprise_linked_users),
            json.dumps(enterprise_linked_users, sort_keys=True, indent=2),
        )
