# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

from enterprise.constants import ENTERPRISE_ROLE_BASED_ACCESS_CONTROL_SWITCH


def create_switch(apps, schema_editor):
    """Create the `role_based_access_control` switch if it does not already exist."""
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.update_or_create(name=ENTERPRISE_ROLE_BASED_ACCESS_CONTROL_SWITCH, defaults={'active': False})


def delete_switch(apps, schema_editor):
    """Delete the `role_based_access_control` switch."""
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.filter(name=ENTERPRISE_ROLE_BASED_ACCESS_CONTROL_SWITCH).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0066_add_system_wide_enterprise_operator_role'),
        ('waffle', '0001_initial')
    ]

    operations = [
        migrations.RunPython(create_switch, delete_switch),
    ]
