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
        for _index, user in enumerate(users[0:11]):
            factories.EnterpriseCustomerUserFactory(
                user_id=user.id,
                enterprise_customer=self.customer,
            )

        # Make a user that is not linked
        factories.EnterpriseCustomerUserFactory(
            user_id=users[11].id,
            enterprise_customer=self.customer,
            linked=False,
        )

        historical_ecu = factories.EnterpriseCustomerUserFactory.create()
        historical_record = historical_ecu.history.create(
            id=historical_ecu.id,
            history_date='2023-01-01 00:00:00',
            history_type='+',
            user_id=historical_ecu.user_id,
            enterprise_customer=historical_ecu.enterprise_customer,
        )

        self.addCleanup(self.cleanup_test_objects)

    def cleanup_test_objects(self):
        """
        Helper to delete all instances of role assignments, ECUs, Enterprise customers, and Users.
        """
        EnterpriseCustomerUser.all_objects.all().delete()
        EnterpriseCustomer.objects.all().delete()
        User.objects.all().delete()

    @patch('enterprise.management.commands.backfill_ecu_table_user_foreign_key.sleep')
    def test_copies_user_id_to_user_fk(self, _):
        ecu = EnterpriseCustomerUser.all_objects.first()
        ecu.user_fk = None

        # use bulk_update to prevent save() method from setting user_fk to user_id
        EnterpriseCustomerUser.all_objects.all().bulk_update([ecu], ['user_fk'])
        ecu.refresh_from_db()
        assert ecu.user_fk is None
        call_command(self.command)
        ecu.refresh_from_db()
        assert ecu.user_fk == ecu.user_id

    @patch('logging.Logger.info')
    @patch('enterprise.management.commands.backfill_ecu_table_user_foreign_key.sleep')
    def test_runs_in_batches(self, mock_sleep, mock_log):
        ecus = EnterpriseCustomerUser.all_objects.all()
        for ecu in ecus:
            ecu.user_fk = None
        EnterpriseCustomerUser.all_objects.all().bulk_update(ecus, ['user_fk'])

        call_command(self.command, batch_limit=3)
        assert mock_sleep.call_count == 6
        mock_log.assert_any_call('Processed 3 records.')
        mock_log.assert_any_call('Processed 6 records.')
        mock_log.assert_any_call('Processed 9 records.')
        mock_log.assert_any_call('Processed 12 records.')

    @patch('enterprise.management.commands.backfill_ecu_table_user_foreign_key.sleep')
    def test_skips_rows_that_already_have_user_fk(self, _):
        ecu = EnterpriseCustomerUser.all_objects.first()
        ecu.user_fk = 9999
        # use bulk_update to prevent save() method from setting user_fk to user_id
        EnterpriseCustomerUser.all_objects.all().bulk_update([ecu], ['user_fk'])
        call_command(self.command)
        assert EnterpriseCustomerUser.all_objects.first().user_fk == 9999

    @patch('enterprise.management.commands.backfill_ecu_table_user_foreign_key.sleep')
    @patch('logging.Logger.warning')
    def test_retry_5_times_on_failure(self, mock_log, _):
        ecus = EnterpriseCustomerUser.all_objects.all()
        for ecu in ecus:
            ecu.user_fk = None
        EnterpriseCustomerUser.all_objects.all().bulk_update(ecus, ['user_fk'])

        with patch(
            ("enterprise.management.commands.backfill_ecu_table_user_foreign_key." +
                "EnterpriseCustomerUser.all_objects.bulk_update"),
            side_effect=DatabaseError(EXCEPTION)
        ):
            with self.assertRaises(Exception):
                call_command(self.command, max_retries=2)
            mock_log.assert_any_call('Attempt 1/2 failed: DUMMY_TRACE_BACK. Retrying in 2s.')
            mock_log.assert_any_call('Attempt 2/2 failed: DUMMY_TRACE_BACK. Retrying in 4s.')

    @patch('enterprise.management.commands.backfill_ecu_table_user_foreign_key.sleep')
    def test_include_unlinked_users(self, _):
        ecus = EnterpriseCustomerUser.all_objects.all()
        for ecu in ecus:
            ecu.user_fk = None
        EnterpriseCustomerUser.all_objects.bulk_update(ecus, ['user_fk'])
        unlinked_ecu = EnterpriseCustomerUser.all_objects.filter(linked=False)[0]
        assert unlinked_ecu.user_fk is None
        call_command(self.command)
        unlinked_ecu.refresh_from_db()
        assert unlinked_ecu.user_fk == unlinked_ecu.user_id

    # test that historical table is also updated
    @patch('enterprise.management.commands.backfill_ecu_table_user_foreign_key.sleep')
    def test_historical_table_is_updated(self, _):
        ecus = EnterpriseCustomerUser.history.all()
        for ecu in ecus:
            ecu.user_fk = None
        EnterpriseCustomerUser.history.bulk_update(ecus, ['user_fk'])
        call_command(self.command)
        ecu = EnterpriseCustomerUser.history.first()
        ecu.refresh_from_db()
        assert ecu.user_fk == ecu.user_id
