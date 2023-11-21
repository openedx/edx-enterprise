"""
Tests for the djagno management command `reencrypt_enterprise_customer_reporting_config_passwords`.
"""
from testfixtures import LogCapture

from django.core.management import call_command
from django.test import TestCase

from enterprise.models import EnterpriseCustomerReportingConfiguration
from test_utils import factories

LOGGER_NAME = 'enterprise.management.commands.reencrypt_enterprise_customer_reporting_config_passwords'


class ReencryptPasswordsTest(TestCase):
    """
    Test command `reencrypt_enterprise_customer_reporting_config_passwords`.
    """
    def test_reencrypt_command(self):
        # Create an instance of EnterpriseCustomerReportingConfiguration
        enterprise_customer = factories.EnterpriseCustomerFactory(name="GriffCo")
        original_config = EnterpriseCustomerReportingConfiguration.objects.create(
            enterprise_customer=enterprise_customer,
            active=True,
            delivery_method=EnterpriseCustomerReportingConfiguration.DELIVERY_METHOD_EMAIL,
            email='test@edx.org',
            decrypted_password='test_password',
            day_of_month=1,
            hour_of_day=1,
        )

        # Assert that the password has been encrypted
        self.assertNotEqual(original_config.encrypted_password, 'test_password')

        with LogCapture(LOGGER_NAME) as log:
            call_command('reencrypt_enterprise_customer_reporting_config_passwords')
            self.assertEqual(
                'Enterprise customer reporting configuration passwords reencrypted succesfully!',
                log.records[0].message
            )
            updated_config = EnterpriseCustomerReportingConfiguration.objects.get(pk=original_config.pk)
            # Assert that the password has been reencrypted
            self.assertNotEqual(updated_config.encrypted_password, updated_config.encrypted_password)
