"""
Management command to send admin invite reminder emails.
"""
from django.core.management.base import BaseCommand

from enterprise.tasks import send_enterprise_admin_invite_reminders


class Command(BaseCommand):
    """
    Management command to send reminder emails for pending enterprise admin invites.
    """

    help = 'Send reminder emails for pending enterprise admin invites.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--async',
            action='store_true',
            dest='run_async',
            default=False,
            help='Run the task asynchronously via Celery.',
        )

    def handle(self, *args, **options):
        if options['run_async']:
            send_enterprise_admin_invite_reminders.delay()
            self.stdout.write('Dispatched send_enterprise_admin_invite_reminders task asynchronously.')
        else:
            send_enterprise_admin_invite_reminders()
            self.stdout.write('Finished sending enterprise admin invite reminders.')
