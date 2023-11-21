"""
Django management command to reencrypt passwords in enterprise custom reporting configs.
"""
import logging

from django.core.management import BaseCommand

from enterprise.models import EnterpriseCustomerReportingConfiguration

LOGGER = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Django management command to reencrypt passwords in enterprise custom reporting configs
    It's useful when following encryption keys are rotated
    - FERNET_KEYS
    - LMS_FERNET_KEY

    Example usage:
    ./manage.py lms reencrypt_enterprise_customer_reporting_config_passwords

    """
    def handle(self, *args, **options):
        try:
            for config in EnterpriseCustomerReportingConfiguration.objects.all():
                config.save()  # resaving reencrypts all the encrypted columns
            LOGGER.info('Enterprise customer reporting configuration passwords reencrypted succesfully!')
        except Exception as e:  # pylint: disable=broad-except
            LOGGER.exception(f'Failed to reencrypt customer reporting configuration passwords. Error: {e}')
