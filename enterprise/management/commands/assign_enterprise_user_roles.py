"""
Management command for assigning enterprise roles to existing enterprise users.
"""
from __future__ import absolute_import, unicode_literals

import logging
from time import sleep

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from enterprise.constants import ENTERPRISE_ADMIN_ROLE, ENTERPRISE_DATA_API_ACCESS_GROUP, ENTERPRISE_LEARNER_ROLE
from enterprise.models import EnterpriseCustomerUser, SystemWideEnterpriseRole, SystemWideEnterpriseUserRoleAssignment

LOGGER = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Management command for assigning enterprise roles to existing enterprise users.

    Example usage:
        $ ./manage.py assign_enterprise_user_roles --role=enterprise_admin
        $ ./manage.py assign_enterprise_user_roles --role=enterprise_learner
    """
    help = 'Assigns enterprise roles to existing enterprise users.'

    def add_arguments(self, parser):
        """
        Entry point for subclassed commands to add custom arguments.
        """
        parser.add_argument(
            '--role',
            action='store',
            dest='role',
            default=None,
            help='Role to assign users role assignments.'
        )
        parser.add_argument(
            '--batch-limit',
            action='store',
            dest='batch_limit',
            default=100,
            help='Number of users in each batch of conditional offer migration.',
            type=int,
        )

        parser.add_argument(
            '--batch-offset',
            action='store',
            dest='batch_offset',
            default=0,
            help='Which index to start batching from.',
            type=int,
        )

        parser.add_argument(
            '--batch-sleep',
            action='store',
            dest='batch_sleep',
            default=10,
            help='How long to sleep between batches.',
            type=int,
        )

    def _get_enterprise_admin_users_batch(self, start, end):
        """
        Returns a batched queryset of User objects.
        """
        LOGGER.info('Fetching new batch of enterprise admin users from indexes: %s to %s', start, end)
        return User.objects.filter(groups__name=ENTERPRISE_DATA_API_ACCESS_GROUP, is_staff=False)[start:end]

    def _get_enterprise_customer_users_batch(self, start, end):
        """
        Returns a batched queryset of EnterpriseCustomerUser objects.
        """
        LOGGER.info('Fetching new batch of enterprise customer users from indexes: %s to %s', start, end)
        return User.objects.filter(pk__in=EnterpriseCustomerUser.objects.values('user_id'))[start:end]

    def _assign_enterprise_role_to_users(self, _get_batch_method, options):
        """
        Assigns enterprise role to users.
        """
        role_name = options['role']
        batch_limit = options['batch_limit']
        batch_sleep = options['batch_sleep']
        batch_offset = options['batch_offset']

        current_batch_index = batch_offset

        users_batch = _get_batch_method(
            batch_offset,
            batch_offset + batch_limit
        )

        enterprise_role = SystemWideEnterpriseRole.objects.get(name=role_name)
        while users_batch.count() > 0:
            for index, user in enumerate(users_batch):
                LOGGER.info(
                    'Processing user with index %s and id %s',
                    current_batch_index + index, user.id
                )
                SystemWideEnterpriseUserRoleAssignment.objects.get_or_create(
                    user=user,
                    role=enterprise_role
                )

            sleep(batch_sleep)
            current_batch_index += len(users_batch)
            users_batch = _get_batch_method(
                current_batch_index,
                current_batch_index + batch_limit
            )

    def handle(self, *args, **options):
        """
        Entry point for managment command execution.
        """
        LOGGER.info('Starting assigning enterprise roles to users!')

        role = options['role']
        if role == ENTERPRISE_ADMIN_ROLE:
            # Assign admin role to non-staff users with enterprise data api access.
            self._assign_enterprise_role_to_users(self._get_enterprise_admin_users_batch, options)
        elif role == ENTERPRISE_LEARNER_ROLE:
            # Assign enterprise learner role to enterprise customer users.
            self._assign_enterprise_role_to_users(self._get_enterprise_customer_users_batch, options)
        else:
            raise CommandError('Please provide a valid role name. Supported roles are {admin} and {learner}'.format(
                admin=ENTERPRISE_ADMIN_ROLE,
                learner=ENTERPRISE_LEARNER_ROLE
            ))

        LOGGER.info('Successfully finished assigning enterprise roles to users!')
