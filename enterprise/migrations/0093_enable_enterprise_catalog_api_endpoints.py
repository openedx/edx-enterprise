# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

from enterprise.constants import USE_ENTERPRISE_CATALOG


def create_flag(apps, schema_editor):
    """Create the 'use_enterprise_catalog' flag if it does not already exist."""
    flag = apps.get_model('waffle', 'Flag')
    flag.objects.get_or_create(
        name=USE_ENTERPRISE_CATALOG,
        defaults={'everyone': None, 'superusers': False},
    )


def delete_flag(apps, schema_editor):
    """Delete the 'use_enterprise_catalog' flag."""
    flag = apps.get_model('waffle', 'Flag')
    flag.objects.filter(name=USE_ENTERPRISE_CATALOG).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('enterprise', '0092_auto_20200312_1650'),
    ]

    operations = [
        migrations.RunPython(create_flag, reverse_code=delete_flag),
    ]
