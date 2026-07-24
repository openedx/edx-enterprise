"""
Management command for seeding a single enterprise customer and its users in devstack.
"""

import json
import logging
import textwrap

from django.core.management.base import BaseCommand

from enterprise.constants import ENTERPRISE_ADMIN_ROLE, ENTERPRISE_LEARNER_ROLE
from enterprise.devstack_api import (
    ensure_enterprise_groups,
    get_or_create_enterprise_catalog,
    get_or_create_enterprise_customer,
    get_or_create_enterprise_user,
    get_or_create_site,
    link_user_to_enterprise,
    seed_global_users,
)

LOGGER = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Management command for populating Devstack with initial data for enterprise.

    Example usage:
        $ ./manage.py lms seed_enterprise_devstack_data
        $ ./manage.py lms seed_enterprise_devstack_data --enterprise-name "Acme Corp"
        $ ./manage.py lms seed_enterprise_devstack_data --no-create-users
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
        parser.add_argument(
            '--no-create-users',
            action='store_true',
            dest='no_create_users',
            default=False,
            help='Skip creating enterprise role users (global and tenant-scoped); '
                 'only seed the enterprise customer, catalog, and groups.',
        )

    def handle(self, *args, **options):
        enterprise_name = options['enterprise_name']

        LOGGER.info('\nEnsuring enterprise-related Django groups exist...')
        ensure_enterprise_groups()

        LOGGER.info('\nCreating a new enterprise customer...')
        site = get_or_create_site()
        enterprise_customer = get_or_create_enterprise_customer(name=enterprise_name, site=site)
        enterprise_catalog = get_or_create_enterprise_catalog(enterprise_customer)

        if options['no_create_users']:
            LOGGER.info('\nSkipping user creation (--no-create-users).')
            LOGGER.info(
                textwrap.dedent(
                    '''\nSuccessfully seeded a new enterprise with the following data:
                    \n| Enterprise Customer: %s (%s)
                    \n| Enterprise Catalog: %s (%s)
                    '''
                ),
                enterprise_customer.name,
                enterprise_customer.uuid,
                enterprise_catalog.title,
                enterprise_catalog.uuid,
            )
            return

        # Global operator/worker/super-admin users apply across all enterprises,
        # so they are seeded once and never linked to a specific enterprise.
        LOGGER.info('\nCreating global enterprise users...')
        seed_global_users()

        LOGGER.info('\nCreating tenant-scoped enterprise users and assigning roles...')
        slug = enterprise_customer.slug
        lms_users = [
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
        ]
        for i in range(2):
            lms_users.append(get_or_create_enterprise_user(
                username=f'{slug}_learner_{i + 1}',
                role=ENTERPRISE_LEARNER_ROLE,
                enterprise_customer=enterprise_customer,
            ))

        LOGGER.info('\nLinking tenant-scoped users to enterprise...')
        serialized_enterprise_linked_users = []
        for lms_user in lms_users:
            if lms_user is None:
                continue
            ecu, _ = link_user_to_enterprise(user=lms_user, enterprise_customer=enterprise_customer)
            serialized_enterprise_linked_users.append({
                'lms_user_id': lms_user.id,
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
            len(serialized_enterprise_linked_users),
            json.dumps(serialized_enterprise_linked_users, sort_keys=True, indent=2),
        )
