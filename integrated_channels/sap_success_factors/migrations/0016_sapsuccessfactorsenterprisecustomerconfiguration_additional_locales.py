# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sap_success_factors', '0015_auto_20180510_1259'),
    ]

    operations = [
        migrations.AddField(
            model_name='sapsuccessfactorsenterprisecustomerconfiguration',
            name='additional_locales',
            field=models.TextField(default='', help_text='A comma-separated list of additional locales.', verbose_name='Additional Locales', blank=True),
        ),
    ]
