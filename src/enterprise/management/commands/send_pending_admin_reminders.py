"""
Management command for sending reminder emails to pending enterprise customer admin users.

This command should be run on a scheduled basis (via cron) to send reminder emails
to admins who have pending invites that are due for a reminder.
"""

import logging

from django.core.management.base import BaseCommand

from enterprise.tasks import send_enterprise_admin_invite_reminders

log = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Management command for sending reminder emails to pending enterprise customer admin users.

    This command calls the enterprise task function directly (synchronously) to send reminders
    to admin invites that are due based on the configured delay and max reminder count.

    Example usage:
        $ ./manage.py lms send_pending_admin_reminders

    This command is intended to be run periodically via cron/Jenkins on a production schedule
    (e.g., hourly or daily).

    For testing in devstack, you can run it manually to trigger reminders.
    """
    help = 'Sends reminder emails to pending enterprise admin invites that are due for reminders.'

    def handle(self, *args, **options):
        """
        Execute the command to send pending admin reminders.
        """
        log.info('Starting send_pending_admin_reminders management command')

        try:
            # Call the task function directly (not via Celery)
            result = send_enterprise_admin_invite_reminders()

            log.info(
                'Completed send_pending_admin_reminders: '
                'processed=%d, sent=%d, skipped_active=%d, skipped_not_due=%d, '
                'skipped_max=%d, failures=%d',
                result.get('processed', 0),
                result.get('sent', 0),
                result.get('skipped_active', 0),
                result.get('skipped_not_due', 0),
                result.get('skipped_max', 0),
                result.get('failures', 0)
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully sent {result.get('sent', 0)} reminder(s) "
                    f"out of {result.get('processed', 0)} pending invite(s)"
                )
            )

        except Exception as exc:
            log.exception('Error executing send_pending_admin_reminders command')
            self.stderr.write(
                self.style.ERROR(f'Failed to send reminders: {str(exc)}')
            )
            raise
