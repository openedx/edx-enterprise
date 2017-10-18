# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sap_success_factors', '0007_remove_historicalsapsuccessfactorsenterprisecustomerconfiguration_history_change_reason'),
    ]

    operations = [
        migrations.AddField(
            model_name='historicalsapsuccessfactorsenterprisecustomerconfiguration',
            name='history_change_reason',
            field=models.CharField(max_length=100, null=True),
        ),
    ]
