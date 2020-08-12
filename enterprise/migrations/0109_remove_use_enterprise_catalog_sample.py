# -*- coding: utf-8 -*-


from django.db import migrations

from enterprise.constants import USE_ENTERPRISE_CATALOG


def create_sample(apps, schema_editor):
    """Create the `use_enterprise_catalog` sample if it does not already exist."""
    Sample = apps.get_model('waffle', 'Sample')
    Sample.objects.get_or_create(
        name=USE_ENTERPRISE_CATALOG,
        defaults={'percent': 100},
    )


def delete_sample(apps, schema_editor):
    """Delete the `use_enterprise_catalog` sample if one exists."""
    Sample = apps.get_model('waffle', 'Sample')
    Sample.objects.filter(name=USE_ENTERPRISE_CATALOG).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0108_add_licensed_enrollment_is_revoked'),
    ]

    operations = [
        migrations.RunPython(delete_sample, create_sample)
    ]
