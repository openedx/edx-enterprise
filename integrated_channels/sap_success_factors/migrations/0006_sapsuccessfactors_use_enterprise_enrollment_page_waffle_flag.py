# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


def create_switch(apps, schema_editor):
    """Create and activate the SAP_USE_ENTERPRISE_ENROLLMENT_PAGE switch if it does not already exist."""
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.get_or_create(name='SAP_USE_ENTERPRISE_ENROLLMENT_PAGE', defaults={'active': False})


def delete_switch(apps, schema_editor):
    """Delete the SAP_USE_ENTERPRISE_ENROLLMENT_PAGE switch."""
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.filter(name='SAP_USE_ENTERPRISE_ENROLLMENT_PAGE').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('sap_success_factors', '0005_historicalsapsuccessfactorsenterprisecustomerconfiguration_history_change_reason'),
        ('waffle', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_switch, reverse_code=delete_switch),
    ]
