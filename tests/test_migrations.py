# -*- coding: utf-8 -*-
"""
Tests for migrations, especially potentially risky data migrations.
"""

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test.testcases import TransactionTestCase


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
