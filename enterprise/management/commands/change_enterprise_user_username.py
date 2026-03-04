"""
Django management command for changing an enterprise user's username.
"""

import logging

from django.contrib.auth import get_user_model
from django.core.management import BaseCommand

from enterprise.models import EnterpriseCustomerUser

User = get_user_model()
LOGGER = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Updates the username value for a given user.

    This is NOT MEANT for general use, and is specifically limited to enterprise users since
    only they could potentially experience the issue of overwritten usernames.

    See ENT-832 for details on the bug that modified usernames for some enterprise users.
    """
    help = 'Update the username of a given user.'

    def add_arguments(self, parser):
        parser.add_argument(
            '-u',
            '--user_id',
            action='store',
            dest='user_id',
            default=None,
            help='The ID of the user to update.'
        )

        parser.add_argument(
            '-n',
            '--new_username',
            action='store',
            dest='new_username',
            default=None,
            help='The username value to set for the user.'
        )

    def handle(self, *args, **options):
        user_id = options.get('user_id')
        new_username = options.get('new_username')

        try:
            EnterpriseCustomerUser.objects.get(user_id=user_id)
        except EnterpriseCustomerUser.DoesNotExist:
            LOGGER.info('User %s must be an enterprise user.', user_id)
            return

        user = User.objects.get(id=user_id)
        user.username = new_username
        user.save()

        LOGGER.info('User %s has been updated with username %s.', user_id, new_username)
