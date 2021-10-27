"""
Tests for the djagno management command `save_enterprise_customer_users`.
"""

from unittest import mock

from pytest import mark

from django.core.management import call_command
from django.db.models.signals import post_save
from django.test import TestCase

from enterprise.models import EnterpriseCustomerUser
from test_utils.factories import EnterpriseCustomerFactory, EnterpriseCustomerUserFactory, UserFactory


@mark.django_db
class SaveEnterpriseCustomerUsersCommandTests(TestCase):
    """
    Test command `save_enterprise_customer_users`.
    """
    command = 'save_enterprise_customer_users'

    def setUp(self):
        self.user_1 = UserFactory.create(is_active=True)
        self.enterprise_customer_1 = EnterpriseCustomerFactory(
            name='Test EnterpriseCustomer 1',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        self.enterprise_customer_user_1 = EnterpriseCustomerUserFactory(
            user_id=self.user_1.id,
            enterprise_customer=self.enterprise_customer_1
        )
        self.user_2 = UserFactory.create(is_active=True)
        self.enterprise_customer_2 = EnterpriseCustomerFactory(
            name='Test EnterpriseCustomer 2',
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent='at_enrollment',
        )
        self.enterprise_customer_user_2 = EnterpriseCustomerUserFactory(
            user_id=self.user_2.id,
            enterprise_customer=self.enterprise_customer_2
        )
        super().setUp()

    @mock.patch('enterprise.management.commands.save_enterprise_customer_users.LOGGER')
    def test_enterprise_customer_user_saved(self, logger_mock):
        """
        Test that the command creates missing EnterpriseCourseEnrollment records.
        """
        post_save_handler = mock.MagicMock()
        post_save.connect(post_save_handler, sender=EnterpriseCustomerUser)

        call_command(self.command)

        logger_mock.info.assert_called_with('%s EnterpriseCustomerUser models saved.', 2)
        post_save_handler.assert_called()

    @mock.patch('enterprise.management.commands.save_enterprise_customer_users.LOGGER')
    def test_enterprise_customer_user_saved_with_option(self, logger_mock):
        """
        Test that the command creates missing EnterpriseCourseEnrollment records.
        """
        call_command(self.command, enterprise_customer_uuid=self.enterprise_customer_1.uuid)

        logger_mock.info.assert_called_with('%s EnterpriseCustomerUser models saved.', 1)
