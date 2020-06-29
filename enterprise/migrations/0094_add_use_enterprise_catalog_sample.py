# -*- coding: utf-8 -*-


from django.db import migrations

from enterprise.constants import USE_ENTERPRISE_CATALOG


def create_sample(apps, schema_editor):
    """Create the `use_enterprise_catalog` sample if it does not already exist."""
    Sample = apps.get_model('waffle', 'Sample')
    Sample.objects.get_or_create(
        name=USE_ENTERPRISE_CATALOG,
        defaults={'percent': 0},
    )


def delete_sample(apps, schema_editor):
    """Delete the `use_enterprise_catalog` sample if one exists."""
    Sample = apps.get_model('waffle', 'Sample')
    Sample.objects.filter(name=USE_ENTERPRISE_CATALOG).delete()


def create_flag(apps, schema_editor):
    """Create the `use_enterprise_catalog` flag if it does not already exist."""
    Flag = apps.get_model('waffle', 'Flag')
    Flag.objects.get_or_create(
        name=USE_ENTERPRISE_CATALOG,
        defaults={'everyone': None, 'superusers': False},
    )


def delete_flag(apps, schema_editor):
    """Delete the `use_enterprise_catalog` flag if one exists."""
    Flag = apps.get_model('waffle', 'Flag')
    Flag.objects.filter(name=USE_ENTERPRISE_CATALOG).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0093_add_use_enterprise_catalog_flag'),
    ]

    operations = [
        migrations.RunPython(delete_flag, create_flag),
        migrations.RunPython(create_sample, delete_sample)
    ]
