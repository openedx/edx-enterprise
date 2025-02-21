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

        for i in range(100):
            factories.UserFactory(username=f'user-{i}')

        self.alpha_customer = factories.EnterpriseCustomerFactory(
            name='alpha',
        )
        self.beta_customer = factories.EnterpriseCustomerFactory(
            name='beta',
        )

        users = User.objects.all()

        # Make a bunch of users for an ENT customer
        for index, user in enumerate(users[0:30]):
            factories.EnterpriseCustomerUserFactory(
                user_id=user.id,
                enterprise_customer=self.alpha_customer,
            )

        # Make a bunch of users for another ENT customer
        for index, user in enumerate(users[30:65]):
            factories.EnterpriseCustomerUserFactory(
                user_id=user.id,
                enterprise_customer=self.beta_customer,
            )

        # Make some users that are NOT LINKED, so we should ignore them
        for index, user in enumerate(users[65:75]):
            ecu = factories.EnterpriseCustomerUserFactory(
                user_id=user.id,
                enterprise_customer=self.alpha_customer,
            )
            ecu.linked = False
            ecu.save()

        # Now make a subset of first set of enterprise customers also have
        # EnterpriseCustomerUser records with a 2nd enterprise customer
        for index, user in enumerate(users[0:15]):
            factories.EnterpriseCustomerUserFactory(
                user_id=user.id,
                enterprise_customer=self.beta_customer,
            )

        self.addCleanup(self.cleanup_test_objects)

    # # def test_user_role_assignments_created(self):
    # #     """
    # #     Verify that the management command correctly creates User Role Assignments
    # #     for enterprise customer users missing them.
    # #     """

    # #     assert EnterpriseCustomerUser.all_objects.count() == 90
    # #     assert SystemWideEnterpriseUserRoleAssignment.objects.filter(
    # #         enterprise_customer=self.alpha_customer
    # #     ).count() == 15
    # #     assert SystemWideEnterpriseUserRoleAssignment.objects.filter(
    # #         enterprise_customer=self.beta_customer
    # #     ).count() == 24

    # #     call_command(
    # #         'backfill_learner_role_assignments',
    # #         '--batch-sleep',
    # #         '0',
    # #         '--batch-limit',
    # #         '10',
    # #     )

    # #     # Notice the discrepancy of values: 90 != 30 + 50
    # #     # That's because 10 ECU records are linked=False, so we dont
    # #     # create a role assignment for them
    # #     assert EnterpriseCustomerUser.all_objects.count() == 90
    # #     assert SystemWideEnterpriseUserRoleAssignment.objects.filter(
    # #         enterprise_customer=self.alpha_customer
    # #     ).count() == 30
    # #     assert SystemWideEnterpriseUserRoleAssignment.objects.filter(
    # #         enterprise_customer=self.beta_customer
    # #     ).count() == 50
    # #     for ecu in EnterpriseCustomerUser.objects.all():
    # #         assert SystemWideEnterpriseUserRoleAssignment.objects.filter(user=ecu.user).exists()

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
    @patch('time.sleep')
    def test_runs_in_batches(self, mock_sleep, mock_log):
        call_command(self.command, batch_limit=10)
        assert mock_sleep.call_count == 8
        assert mock_log.called_with('Updated %d EnterpriseCustomerUser records', 10)

    def test_skips_rows_that_already_have_user_fk(self):
        ecu = EnterpriseCustomerUser.objects.first()
        ecu.user_fk = -1
        ecu.save()
        call_command(self.command)
        assert EnterpriseCustomerUser.objects.first().user_fk == -1

    # def test_times_out_after_5_seconds_per_batch(self):

    # def test_retry_5_times_on_failure(self):

    # def test_logs_progress_and_errors(self):
