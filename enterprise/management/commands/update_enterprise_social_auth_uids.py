"""
Django management command to update the social auth records UID
"""

import csv
import logging

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand
from django.db import transaction

try:
    from social_django.models import UserSocialAuth
except ImportError:
    UserSocialAuth = None

logger = logging.getLogger(__name__)


class CSVUpdateError(Exception):
    """Custom exception for CSV update process."""
    pass  # pylint: disable=unnecessary-pass


class Command(BaseCommand):
    """
    Update the enterprise related social auth records UID to the new one.

    Example usage:
    ./manage.py lms update_enterprise_social_auth_uids csv_file_path
    ./manage.py lms update_enterprise_social_auth_uids csv_file_path --old-prefix="slug:" --new-prefix="slug:x|{}@xyz"
    ./manage.py lms update_enterprise_social_auth_uids csv_file_path --no-dry-run

    """

    help = 'Records update from CSV with console logging'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to the CSV file')
        parser.add_argument(
            '--old_prefix',
            type=str,
            default=None,
            help='Optional old prefix for old UID. If not provided, uses CSV value.'
        )
        parser.add_argument(
            '--new_prefix',
            type=str,
            default=None,
            help='Optional new prefix for new UID. If not provided, uses CSV value.'
        )
        parser.add_argument(
            '--no-dry-run',
            action='store_false',
            dest='dry_run',
            default=True,
            help='Actually save changes instead of simulating'
        )

    def handle(self, *args, **options):
        logger.info("Command has started...")
        csv_path = options['csv_file']
        dry_run = options['dry_run']
        old_prefix = options['old_prefix']
        new_prefix = options['new_prefix']

        total_processed = 0
        total_updated = 0
        total_errors = 0

        try:
            with open(csv_path, 'r') as csvfile:
                reader = csv.DictReader(csvfile)

                for row_num, row in enumerate(reader, start=1):
                    total_processed += 1

                    try:
                        with transaction.atomic():
                            if self.update_record(row, dry_run, old_prefix, new_prefix):
                                total_updated += 1

                    except Exception as row_error:  # pylint: disable=broad-except
                        total_errors += 1
                        error_msg = f"Row {row_num} update failed: {row} - Error: {str(row_error)}"
                        logger.error(error_msg, exc_info=True)

            summary_msg = (
                f"CSV Update Summary:\n"
                f"Total Records Processed: {total_processed}\n"
                f"Records Successfully Updated: {total_updated}\n"
                f"Errors Encountered: {total_errors}\n"
                f"Dry Run Mode: {'Enabled' if dry_run else 'Disabled'}"
            )
            logger.info(summary_msg)
        except IOError as io_error:
            logger.critical(f"File I/O error: {str(io_error)}")

        except Exception as e:  # pylint: disable=broad-except
            logger.critical(f"Critical error in CSV processing: {str(e)}")

    def update_record(self, row, dry_run=True, old_prefix=None, new_prefix=None):
        """
        Update a single record, applying optional prefixes to UIDs if provided.

        Args:
            row (dict): CSV row data
            dry_run (bool): Whether to simulate or actually save changes
            old_prefix (str): Prefix to apply to the old UID
            new_prefix (str): Prefix to apply to the new UID

        Returns:
            bool: Whether the update was successful
        """
        try:
            old_uid = row.get('old-uid')
            new_uid = row.get('new-uid')

            # Validating that both values are present
            if not old_uid or not new_uid:
                raise CSVUpdateError("Missing required UID fields")

            # Construct dynamic UIDs
            old_uid_with_prefix = f'{old_prefix}{old_uid}' if old_prefix else old_uid
            new_uid_with_prefix = (
                new_prefix.format(new_uid) if new_prefix and '{}' in new_prefix
                else f"{new_prefix}{new_uid}" if new_prefix
                else new_uid
            )

            instance_with_old_uid = UserSocialAuth.objects.filter(uid=old_uid_with_prefix).first()

            if not instance_with_old_uid:
                raise CSVUpdateError(f"No record found with old UID {old_uid_with_prefix}")

            instance_with_new_uid = UserSocialAuth.objects.filter(uid=new_uid_with_prefix).first()
            if instance_with_new_uid:
                log_entry = f"Warning: Existing record with new UID {new_uid_with_prefix} is deleting."
                logger.info(log_entry)
                if not dry_run:
                    instance_with_new_uid.delete()

            if not dry_run:
                instance_with_old_uid.uid = new_uid_with_prefix
                instance_with_old_uid.save()

            log_entry = f"Successfully updated record: Old UID {old_uid_with_prefix} → New UID {new_uid_with_prefix}"
            logger.info(log_entry)

            return True

        except ValidationError as ve:
            error_msg = f"Validation error: {ve}"
            logger.error(error_msg)
            raise

        except CSVUpdateError as update_error:
            error_msg = f"Update processing error: {update_error}"
            logger.error(error_msg)
            raise

        except Exception as e:
            error_msg = f"Unexpected error during record update: {e}"
            logger.error(error_msg, exc_info=True)
            raise
