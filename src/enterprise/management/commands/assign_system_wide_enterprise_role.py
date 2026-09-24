"""
Management command for assigning a system-wide enterprise role to an existing user.
"""

import logging

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from enterprise import roles_api
from enterprise.models import EnterpriseCustomer

LOGGER = logging.getLogger(__name__)
User = get_user_model()


class Command(BaseCommand):
    """
    Assign a system-wide enterprise role to an existing user.

    The user must already exist (this command never creates it). Exactly one of
    --all-contexts or --enterprise-customer must be given.

    Example usage:
        $ ./manage.py lms assign_system_wide_enterprise_role \
              --username enterprise_worker \
              --role enterprise_openedx_operator \
              --all-contexts
        $ ./manage.py lms assign_system_wide_enterprise_role \
              --username admin_acme \
              --role enterprise_admin \
              --enterprise-customer acme-corp
    """

    help = 'Assign a system-wide enterprise role to an existing user.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            required=True,
            help='Username of the existing user to assign the role to.',
        )
        parser.add_argument(
            '--role',
            required=True,
            help='System-wide role name, e.g. enterprise_openedx_operator.',
        )
        scope = parser.add_mutually_exclusive_group(required=True)
        scope.add_argument(
            '--all-contexts',
            action='store_true',
            dest='all_contexts',
            help='Assign the role across all enterprise contexts.',
        )
        scope.add_argument(
            '--enterprise-customer',
            dest='enterprise_customer',
            metavar='SLUG_OR_UUID',
            help='Slug or UUID of the enterprise customer to scope the role to.',
        )

    def handle(self, *args, **options):
        username = options['username']
        role = options['role']

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist as exc:
            raise CommandError(f"User '{username}' does not exist.") from exc

        enterprise_customer = None
        if options['enterprise_customer']:
            enterprise_customer = self._resolve_enterprise_customer(options['enterprise_customer'])

        try:
            assignment, created = roles_api.assign_role(
                user=user,
                role_name=role,
                enterprise_customer=enterprise_customer,
                applies_to_all_contexts=options['all_contexts'],
            )
        except roles_api.UnknownSystemWideRoleError as exc:
            raise CommandError(f"Role '{role}' is not a recognised system-wide enterprise role.") from exc
        LOGGER.info(
            '%s system-wide role assignment: user=%s role=%s scope=%s',
            'Created' if created else 'Found existing',
            user.username,
            role,
            'all-contexts' if options['all_contexts'] else enterprise_customer.slug,
        )
        return str(assignment.pk)

    def _resolve_enterprise_customer(self, identifier):
        """Return the EnterpriseCustomer matching identifier by slug, else by UUID."""
        try:
            return EnterpriseCustomer.objects.get(slug=identifier)
        except EnterpriseCustomer.DoesNotExist:
            pass
        try:
            return EnterpriseCustomer.objects.get(uuid=identifier)
        except (EnterpriseCustomer.DoesNotExist, ValidationError, ValueError) as exc:
            raise CommandError(
                f"EnterpriseCustomer with slug or UUID '{identifier}' does not exist."
            ) from exc
