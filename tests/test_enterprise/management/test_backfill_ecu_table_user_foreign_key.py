"""
Tests for the Django management command `backfill_ecu_table_user_foreign_key`.
"""

from unittest.mock import patch

import ddt
import factory
from pytest import mark

from django.contrib import auth
from django.core.management import call_command
from django.db import DatabaseError
from django.db.models import signals
from django.test import TestCase

from enterprise.models import EnterpriseCustomer, EnterpriseCustomerUser
from test_utils import factories

EXCEPTION = "DUMMY_TRACE_BACK"

User = auth.get_user_model()


@mark.django_db
@ddt.ddt
class CreateEnterpriseCourseEnrollmentCommandTests(TestCase):
    """
    Test command `backfill_ecu_table_user_foreign_key`.
    """
    command = 'backfill_ecu_table_user_foreign_key'

    @factory.django.mute_signals(signals.post_save)
    def setUp(self):
        super().setUp()
        self.cleanup_test_objects()

        for i in range(12):
            factories.UserFactory(username=f'user-{i}')

        self.customer = factories.EnterpriseCustomerFactory(
            name='alpha',
        )

        users = User.objects.all()

        # Make a bunch of users for an ENT customer
        for _index, user in enumerate(users[0:12]):
            factories.EnterpriseCustomerUserFactory(
                user_id=user.id,
                enterprise_customer=self.customer,
            )

        self.addCleanup(self.cleanup_test_objects)

    def cleanup_test_objects(self):
        """
        Helper to delete all instances of role assignments, ECUs, Enterprise customers, and Users.
        """
        EnterpriseCustomerUser.objects.all().delete()
        EnterpriseCustomer.objects.all().delete()
        User.objects.all().delete()


    # def test_on_create_should_set_user_fk_to_user(self):
    #     """Test that user_fk is set to user_id when creating a record."""
    #     user = factories.UserFactory(email='email@example.com')
    #     enterprise_customer_user = factories.EnterpriseCustomerUserFactory(user_id=user.id)

    #     assert enterprise_customer_user.user_fk == user, (
    #         f"Expected user_fk to be User with id {user.id}, but got {enterprise_customer_user.user_fk}"
    #     )
    #     ecu = EnterpriseCustomerUser.objects.first()
    #     ecu.user_fk = None


    def test_copies_user_id_to_user_fk(self):
        user = factories.UserFactory(email='email@example.com')
        ecu = factories.EnterpriseCustomerUserFactory(user_id=user.id)
        ecu.user_fk = None

        # use bulk_update to prevent save() method from setting user_fk to user_id
        EnterpriseCustomerUser.objects.all().bulk_update([ecu], ['user_fk'])
        ecu.refresh_from_db()
        assert ecu.user_fk is None
        call_command(self.command)
        ecu.refresh_from_db()
        assert ecu.user_fk == user

    @patch('logging.Logger.info')
    @patch('enterprise.management.commands.backfill_ecu_table_user_foreign_key.sleep')
    def test_runs_in_batches(self, mock_sleep, mock_log):
        ecus = EnterpriseCustomerUser.objects.all()
        for ecu in ecus:
            ecu.user_fk = None
        EnterpriseCustomerUser.objects.all().bulk_update(ecus, ['user_fk'])

        call_command(self.command, batch_limit=3)
        assert mock_sleep.call_count == 4
        mock_log.assert_any_call('Processed 3 records.')
        mock_log.assert_any_call('Processed 6 records.')
        mock_log.assert_any_call('Processed 9 records.')
        mock_log.assert_any_call('Processed 12 records.')

    def test_skips_rows_that_already_have_user_fk(self):
        user = factories.UserFactory(email='email@example.com')
        ecu = EnterpriseCustomerUser.objects.first()
        ecu.user_fk = user
        # use bulk_update to prevent save() method from setting user_fk to user_id
        EnterpriseCustomerUser.objects.all().bulk_update([ecu], ['user_fk'])
        call_command(self.command)
        assert EnterpriseCustomerUser.objects.first().user_fk == user

    @patch('logging.Logger.warning')
    def test_retry_5_times_on_failure(self, mock_log):
        ecus = EnterpriseCustomerUser.objects.all()
        for ecu in ecus:
            ecu.user_fk = None
        EnterpriseCustomerUser.objects.all().bulk_update(ecus, ['user_fk'])

        with patch(
            ("enterprise.management.commands.backfill_ecu_table_user_foreign_key." +
                "EnterpriseCustomerUser.objects.bulk_update"),
            side_effect=DatabaseError(EXCEPTION)
        ):
            with self.assertRaises(Exception):
                call_command(self.command, max_retries=2)
            mock_log.assert_any_call('Attempt 1/2 failed: DUMMY_TRACE_BACK. Retrying in 2s.')
            mock_log.assert_any_call('Attempt 2/2 failed: DUMMY_TRACE_BACK. Retrying in 4s.')
