"""
Tests for the Django management command `backfill_ecu_table_user_foreign_key`.
"""

import ddt
import factory
from pytest import mark
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.contrib import auth
from django.db.models import signals

from enterprise.models import EnterpriseCustomerUser, EnterpriseCustomer
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

        for i in range(10):
            factories.UserFactory(username=f'user-{i}')

        self.customer = factories.EnterpriseCustomerFactory(
            name='alpha',
        )

        users = User.objects.all()

        # Make a bunch of users for an ENT customer
        for index, user in enumerate(users[0:10]):
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

    def test_copies_user_id_to_user_fk(self):
        assert EnterpriseCustomerUser.objects.first().user_fk is None
        call_command(self.command)
        assert EnterpriseCustomerUser.objects.first().user_fk is EnterpriseCustomerUser.objects.first().user_id

    @patch('logging.Logger.info')
    @patch('enterprise.management.commands.backfill_ecu_table_user_foreign_key.sleep')
    def test_runs_in_batches(self, mock_sleep, mock_log):
        call_command(self.command, batch_limit=3)
        assert mock_sleep.call_count == 4
        mock_log.assert_any_call('Processed 3/10 rows.')
        mock_log.assert_any_call('Processed 6/10 rows.')
        mock_log.assert_any_call('Processed 9/10 rows.')
        mock_log.assert_any_call('Processed 10/10 rows.')

    def test_skips_rows_that_already_have_user_fk(self):
        ecu = EnterpriseCustomerUser.objects.first()
        ecu.user_fk = 9999
        ecu.save()
        call_command(self.command)
        assert EnterpriseCustomerUser.objects.first().user_fk == 9999

    @patch('logging.Logger.warning')
    def test_retry_5_times_on_failure(self, mock_log):
        with patch(
            ("enterprise.management.commands.backfill_ecu_table_user_foreign_key."
            "EnterpriseCustomerUser.objects.bulk_update"),
            side_effect=Exception(EXCEPTION)
        ):
            with self.assertRaises(Exception) as e:
                call_command(self.command, max_retries=5)
            assert mock_log.called_with(f"Attempt 1/5 failed: {e}. Retrying in 2s.")
            assert mock_log.called_with(f"Attempt 2/5 failed: {e}. Retrying in 2s.")
