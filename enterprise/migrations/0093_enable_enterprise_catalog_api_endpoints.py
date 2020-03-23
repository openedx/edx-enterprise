# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


def create_switch(apps, schema_editor):
    """Create and activate the ENTERPRISE_CATALOG_API_ENDPOINTS_ENABLED switch if it does not already exist."""
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.get_or_create(name='ENTERPRISE_CATALOG_API_ENDPOINTS_ENABLED', defaults={'active': False})


def delete_switch(apps, schema_editor):
    """Delete the ENTERPRISE_CATALOG_API_ENDPOINTS_ENABLED switch."""
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.filter(name='ENTERPRISE_CATALOG_API_ENDPOINTS_ENABLED').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('enterprise', '0092_auto_20200312_1650'),
    ]

    operations = [
        migrations.RunPython(create_switch, reverse_code=delete_switch),
    ]
