"""
Tests for migrations, especially potentially risky data migrations.
"""
from io import StringIO

from django.core.management import call_command
from django.test.testcases import TestCase
from django.test.utils import override_settings


class MigrationTests(TestCase):
    """
    Runs migration tests using Django Command interface.
    """

    @override_settings(MIGRATION_MODULES={})
    def test_migrations_are_in_sync(self):
        out = StringIO()
        call_command("makemigrations", dry_run=True, verbosity=3, stdout=out)
        output = out.getvalue()
        self.assertIn("No changes detected", output)
