"""
Management command for creating a learner linked to one or more enterprise customers.
"""

import logging

from django.core.management.base import BaseCommand, CommandError

from enterprise.devstack_api import get_or_create_user, link_user_to_enterprise
from enterprise.models import EnterpriseCustomer

LOGGER = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Management command for creating a learner linked to one or more enterprise customers.

    The first --enterprise-name is set as the active enterprise; all subsequent ones are inactive.
    Useful for testing multi-enterprise scenarios such as active-enterprise mismatch.

    Example usage:
        $ ./manage.py lms create_enterprise_linked_learner \
              --username dual_linked_learner \
              --enterprise-name "Test Enterprise" \
              --enterprise-name "Other Enterprise"
    """

    help = 'Create a learner user and link them to one or more enterprise customers.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            required=True,
            help='Username of the learner to create or retrieve.',
        )
        parser.add_argument(
            '--enterprise-name',
            action='append',
            dest='enterprise_names',
            required=True,
            metavar='ENTERPRISE_NAME',
            help=(
                'Name of an enterprise customer to link the learner to. '
                'Repeatable. The first value is set as the active enterprise; '
                'all subsequent values are inactive.'
            ),
        )

    def handle(self, *args, **options):
        username = options['username']
        enterprise_names = options['enterprise_names']

        if len(set(enterprise_names)) != len(enterprise_names):
            raise CommandError(
                "Duplicate --enterprise-name values are not allowed. "
                "Passing the same enterprise twice would overwrite the link and flip it inactive."
            )

        user = get_or_create_user(username)

        for index, name in enumerate(enterprise_names):
            try:
                enterprise_customer = EnterpriseCustomer.objects.get(name=name)
            except EnterpriseCustomer.DoesNotExist as exc:
                raise CommandError(f"EnterpriseCustomer with name '{name}' does not exist.") from exc
            link_user_to_enterprise(user, enterprise_customer, active=index == 0)

        LOGGER.info(
            'Done. User %s linked to %d enterprise(s). Active: %s',
            username, len(enterprise_names), enterprise_names[0],
        )
