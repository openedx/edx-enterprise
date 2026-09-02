"""
Management command for updating enterprise user role assignments
with appropriate ``enterprise_customer`` and ``applies_to_all_contexts`` values.
"""

import logging
from collections import defaultdict

from django.contrib import auth
from django.core.management.base import BaseCommand

from enterprise import roles_api
from enterprise.config.models import UpdateRoleAssignmentsWithCustomersConfig
from enterprise.constants import (
    ENTERPRISE_ADMIN_ROLE,
    ENTERPRISE_LEARNER_ROLE,
    ENTERPRISE_OPERATOR_ROLE,
    SYSTEM_ENTERPRISE_CATALOG_ADMIN_ROLE,
)
from enterprise.models import EnterpriseCustomerUser, SystemWideEnterpriseUserRoleAssignment
from enterprise.utils import batch

log = logging.getLogger(__name__)
User = auth.get_user_model()


# pylint: disable=logging-fstring-interpolation
class Command(BaseCommand):
    """
    Management command for creating enterprise role assignments
    with a foreign key to an EnterpriseCustomer, or an explicit boolean
    flag indicating that the assignment grants the role to the user
    for every EnterpriseCustomer.
    """
    help = """
    Applies explicit enterprise customer context for enterprise admin, learner, and catalog system role assignments.
    It also sets `applies_to_all_contexts` to true for assignments of the `enterprise_openedx_operator` role.
    Example usage:
      # Do a dry run for admin assignments of some customer
      ./manage.py lms update_role_assignments_with_customers --role=enterprise_admin --dry-run --enterprise-customer-uuid=00000000-1111-2222-3333-444444444444
      # Do a real run for all operators
      ./manage.py lms update_role_assignments_with_customers --role=enterprise_openedx_operator
      # Process everything for everyone
      ./manage.py lms update_role_assignments_with_customers
    """

    def add_arguments(self, parser):
        """
        Entry point for subclassed commands to add custom arguments.
        """
        parser.add_argument(
            '--role',
            action='store',
            dest='role',
            default=None,
            help='Specifies which user role assignments to update.  If unspecified, will update for all roles.'
        )
        parser.add_argument(
            '--batch-size',
            action='store',
            dest='batch_size',
            default=500,
            help='Number of user role asssignments to update in each batch of updates.',
            type=int,
        )
        parser.add_argument(
            '--enterprise-customer-uuid',
            action='store',
            dest='enterprise_customer_uuid',
            help='The enterprise customer to limit role assignments to.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            dest='dry_run',
            help=(
                'If set, no updates or creates will occur; will instead iterate over '
                'the assignments that would be modified or created'
            ),
        )
        parser.add_argument(
            '--undo',
            action='store_true',
            dest='undo',
        )
        parser.add_argument(
            '--args-from-database',
            action='store_true',
            dest='args_from_database',
            help='If true, read arguments from a DB config model.',
        )

    def handle(self, *args, **options):
        """
        Entry point for managment command execution.
        """
        valid_roles = (
            ENTERPRISE_ADMIN_ROLE,
            ENTERPRISE_LEARNER_ROLE,
            ENTERPRISE_OPERATOR_ROLE,
            SYSTEM_ENTERPRISE_CATALOG_ADMIN_ROLE,
        )

        if options['args_from_database']:
            options.update(self._latest_settings_from_db())

        if not options['role']:
            for role in valid_roles:
                self._handle(
                    options['batch_size'],
                    role,
                    enterprise_customer_uuid=options.get('enterprise_customer_uuid', None),
                    dry_run=options['dry_run']
                )
        elif options['role'] in valid_roles:
            self._handle(
                options['batch_size'],
                options['role'],
                enterprise_customer_uuid=options.get('enterprise_customer_uuid', None),
                dry_run=options['dry_run'],
            )
        else:
            log.error(f"{options['role']} is not a valid role.")

    def _handle(self, batch_size, role_name, enterprise_customer_uuid=None, dry_run=False):
        """
        Does all of the actual work on assignments of a given role.
        """
        if role_name == ENTERPRISE_OPERATOR_ROLE:
            self._handle_operators(dry_run)
            return

        ent_customer_user_ids = self._get_all_enterprise_customer_user_ids(enterprise_customer_uuid)

        log.info(f'There are {len(ent_customer_user_ids)} total enterprise customer user ids to process.')

        for ecu_ids_batch in batch(ent_customer_user_ids, batch_size=batch_size):
            log.info(f'Processing batch of ECU ids between {ecu_ids_batch[0]} and {ecu_ids_batch[-1]}.')

            customers_by_user_id = self._get_customers_by_user_id(ecu_ids_batch)

            assignments_by_user_id_role = self._get_role_assignments_by_user_id_and_role(
                customers_by_user_id.keys(),
                role_name,
            )
            log.info(
                f'There are {len(assignments_by_user_id_role)} assignments '
                f'of the {role_name} role to process in this batch'
            )
            self._handle_non_operators(
                customers_by_user_id,
                assignments_by_user_id_role,
                dry_run,
            )

    def _handle_operators(self, dry_run):
        """
        If not a dry run, modifies all enterprise_openedx_operator role assignments
        to have `applies_to_all_contexts` set to True (because it's implied that a user with the operator role
        has that role for all contexts/customers).

        If `dry_run` is true, we don't perform a database update; instead, a message will be logged
        indicating how many assignments would be updated.
        """
        updated_assignments = []
        queryset = SystemWideEnterpriseUserRoleAssignment.objects.filter(role__name=ENTERPRISE_OPERATOR_ROLE)
        for assignment in queryset:
            assignment.applies_to_all_contexts = True
            updated_assignments.append(assignment)

        log.info(f'There are {len(updated_assignments)} operator role assignments to update.')
        if not dry_run:
            SystemWideEnterpriseUserRoleAssignment.objects.bulk_update(
                updated_assignments,
                ['applies_to_all_contexts'],
                batch_size=100,
            )
            log.info('All operator role assignments have been updated.')

    def _handle_non_operators(self, customers_by_user_id, assignments_by_user_id_role, dry_run):
        """
        For a given mapping of users to enterprise customers, and (user, role) to assignments,
        this method creates one SystemWideEnterpriseUserRoleAssignment per user-customer link,
        with a role based on the `assignments_by_user_id_role` mapping.
        """
        # we'll bulk create the new objects in the DB after we loop through the assignment-user mapping
        assignments_to_create = []

        roles_by_name = roles_api.roles_by_name()

        for (user_id, role_name), role_assignment_set in assignments_by_user_id_role.items():
            linked_customers_by_uuid = {
                customer.uuid: customer for customer in customers_by_user_id[user_id]
            }

            # Some users may already have a role explicitly associated with an enterprise customer,
            # so we first compute the difference between explicit assignments and all linked enterprises.
            existing_customer_assignments = {
                assignment.enterprise_customer.uuid for assignment in role_assignment_set
                if assignment.enterprise_customer
            }
            customer_uuids_to_assign = list(set(linked_customers_by_uuid.keys()) - existing_customer_assignments)
            if not customer_uuids_to_assign:
                continue

            for customer_uuid in customer_uuids_to_assign:
                assignments_to_create.append(
                    SystemWideEnterpriseUserRoleAssignment(
                        user_id=user_id,
                        role=roles_by_name[role_name],
                        enterprise_customer=linked_customers_by_uuid[customer_uuid],
                    )
                )

        log.info(
            f'There are {len(assignments_to_create)} assignments to create in this batch.'
        )

        if dry_run:
            log.info('This is a dry run, no updates or creates will happen for this batch.')
            return

        SystemWideEnterpriseUserRoleAssignment.objects.bulk_create(
            assignments_to_create, batch_size=100
        )

    def _get_all_enterprise_customer_user_ids(self, enterprise_customer_uuid=None):
        """
        Returns a list of all `EnterpriseCustomerUser` ids, or, if `enterprise_customer_uuid` is not null,
        a list of all such ids related to the customer with the given UUID.
        """
        ecu_queryset = EnterpriseCustomerUser.objects.all()
        if enterprise_customer_uuid:
            ecu_queryset = EnterpriseCustomerUser.objects.filter(enterprise_customer__uuid=enterprise_customer_uuid)

        return ecu_queryset.order_by('id').values_list('id', flat=True)

    def _get_customers_by_user_id(self, enterprise_customer_user_ids):
        """
        Returns a mapping of auth.User ids to a set of EnterpriseCustomers
        the user is linked to.
        """
        queryset = EnterpriseCustomerUser.objects.filter(
            id__in=enterprise_customer_user_ids
        )
        customers_by_user_id = defaultdict(set)
        for ecu in queryset:
            customers_by_user_id[ecu.user_id].add(ecu.enterprise_customer)

        return customers_by_user_id

    def _get_role_assignments_by_user_id_and_role(self, user_ids, role_name):
        """
        Returns a mapping of (auth.User id, role name) to a set of SystemWideEnterpriseUserRoleAssignment objects
        associated with that user and role.
        """
        role_assignment_kwargs = {
            'user_id__in': user_ids,
            'role__name': role_name,
            'applies_to_all_contexts': False,
        }

        assignments_by_user_id_role = defaultdict(set)
        for assignment in SystemWideEnterpriseUserRoleAssignment.objects.filter(**role_assignment_kwargs):
            assignments_by_user_id_role[
                (assignment.user_id, assignment.role.name)
            ].add(assignment)

        return assignments_by_user_id_role

    def _latest_settings_from_db(self):
        """
        Return the latest settings from the model-defined settings
        for this management command.
        """
        config = UpdateRoleAssignmentsWithCustomersConfig.current()
        return {
            'role': config.role,
            'batch_size': config.batch_size,
            'enterprise_customer_uuid': config.enterprise_customer_uuid,
            'dry_run': config.dry_run,
        }
