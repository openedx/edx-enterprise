"""
Tests for migrations, especially potentially risky data migrations.
"""
from importlib.metadata import version
from io import StringIO

import pytest

from django.core.management import call_command
from django.test.testcases import TestCase
from django.test.utils import override_settings

GET_DJANGO_VERSION = int(version('django').split('.')[0])


@pytest.mark.skipif(GET_DJANGO_VERSION > 3, reason="django4.2 brings new migrations, so only run for dj32 for now.")
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
