# -*- coding: utf-8 -*-
"""
Tests for migrations, especially potentially risky data migrations.
"""

from __future__ import absolute_import, unicode_literals

import ddt
from consent.models import DataSharingConsent

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test.testcases import TransactionTestCase

from enterprise.decorators import ignore_warning
from enterprise.models import UserDataSharingConsentAudit
from test_utils import factories


class MigrationTestCase(TransactionTestCase):
    """
    A base test case class for migration test cases.
    """

    migrate_origin = None
    migrate_dest = None
    model = None

    def setUp(self):
        super(MigrationTestCase, self).setUp()
        self.executor = MigrationExecutor(connection)
        self.executor.migrate(self.migrate_origin)

    def migrate_to_origin(self):
        """
        Performs the migration to the designated origin.

        This only really does anything if you have migrated forward
        in some way or no migrations were performed at all.
        """
        self.executor.loader.build_graph()
        self.executor.migrate(self.migrate_origin)

    def migrate_to_dest(self):
        """
        Performs the migration to the designated destination.
        """
        self.executor.loader.build_graph()
        self.executor.migrate(self.migrate_dest)

    def migrate_to_dest_then_origin(self):
        """
        Migrates to the destination and back to the origin.

        Can be used as a shortcut to test a forward- and backward-migration in one-go.
        """
        self.migrate_to_dest()
        self.migrate_to_origin()

    @property
    def old_apps(self):
        """
        Returns the app in its original state -- the one that'd exist before migration.
        """
        return self.executor.loader.project_state(self.migrate_origin).apps

    @property
    def new_apps(self):
        """
        Returns the app in a future state -- the one that'd exist after migration.
        """
        return self.executor.loader.project_state(self.migrate_dest).apps

    @property
    def model_label(self):
        """
        Returns the label of the ``model``.
        """
        return self.model._meta.get_field('name')


@ddt.ddt
class MigrateToNewDataSharingConsentTest(MigrationTestCase):
    """
    Test cases for migrating data from ``EnterpriseCourseEnrollment`` and ``UserDataSharingConsentAudit`` to
    the new Consent application's ``DataSharingConsent`` model.
    """

    migrate_origin = [('consent', '0001_initial')]
    migrate_dest = [('consent', '0002_migrate_to_new_data_sharing_consent')]
    model = DataSharingConsent

    def setUp(self):
        """
        Set up EnterpriseCourseEnrollment and UserDataSharingConsentAudit with some data.
        """
        super(MigrateToNewDataSharingConsentTest, self).setUp()
        self.user = factories.UserFactory(
            username='bob',
            id=1
        )
        self.enterprise_customer_user = factories.EnterpriseCustomerUserFactory(
            user_id=1
        )
        self.enterprise_course_enrollment = factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_customer_user
        )
        self.user_data_sharing_consent_audit = factories.UserDataSharingConsentAuditFactory(
            user=self.enterprise_customer_user
        )
        self.migrate_to_origin()

    def tearDown(self):
        """
        Make sure to migrate back to the origin.
        """
        super(MigrateToNewDataSharingConsentTest, self).setUp()
        self.migrate_to_origin()

    @ddt.data(
        (True, UserDataSharingConsentAudit.NOT_SET),
        (True, UserDataSharingConsentAudit.ENABLED),
        (True, UserDataSharingConsentAudit.DISABLED),
        (True, UserDataSharingConsentAudit.EXTERNALLY_MANAGED),
        (False, UserDataSharingConsentAudit.NOT_SET),
        (False, UserDataSharingConsentAudit.ENABLED),
        (False, UserDataSharingConsentAudit.DISABLED),
        (False, UserDataSharingConsentAudit.EXTERNALLY_MANAGED),
        (None, UserDataSharingConsentAudit.NOT_SET),
        (None, UserDataSharingConsentAudit.ENABLED),
        (None, UserDataSharingConsentAudit.DISABLED),
        (None, UserDataSharingConsentAudit.EXTERNALLY_MANAGED),
    )
    @ddt.unpack
    @ignore_warning(DeprecationWarning)
    def test_enrollment_consent_transfers(self, ece_consent_state, udsca_consent_state):
        """
        Test that ``EnterpriseCourseEnrollment``'s consent data transfers over to ``DataSharingConsent``.

        We check ``UserDataSharingConsentAudit`` as a last resort for consent state.
        """
        self.enterprise_course_enrollment.consent_granted = ece_consent_state
        self.enterprise_course_enrollment.save()
        self.user_data_sharing_consent_audit.state = udsca_consent_state
        self.user_data_sharing_consent_audit.save()

        self.migrate_to_dest()

        data_sharing_consent = DataSharingConsent.objects.all().first()
        if self.enterprise_course_enrollment.consent_available:
            self.assertTrue(data_sharing_consent.granted)
        else:
            self.assertFalse(data_sharing_consent.granted)

    @ignore_warning(DeprecationWarning)
    def test_duplicate_consent_doesnt_cause_error(self):
        """
        An existing ``DataSharingConsent`` row shouldn't cause a migration error -- it should update accordingly.
        """
        DataSharingConsent.objects.create(
            username=self.enterprise_customer_user.username,
            course_id=self.enterprise_course_enrollment.course_id,
            enterprise_customer=self.enterprise_customer_user.enterprise_customer,
            granted=False,
        )

        self.enterprise_course_enrollment.consent_granted = True
        self.enterprise_course_enrollment.save()

        self.migrate_to_dest()

        data_sharing_consent = DataSharingConsent.objects.all().first()
        assert data_sharing_consent.granted
